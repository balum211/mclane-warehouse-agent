"""Fulfillment tools: order status, wave progress vs cutoff, short picks, wave release sequencing."""

from __future__ import annotations

from datetime import datetime, timedelta

from .. import db
from .common import (SHIFT_WINDOWS, as_of, dc_clause, error, in_clause, now, ok, parse_date, parse_dt,
                     pct, r1)

DEFAULT_PICK_RATE = 150.0  # cases/hour/picker when no live rate is available


def get_order_fulfillment_summary(dc_id: str = "", ship_date: str = "tomorrow") -> dict:
    """Order and line status for a ship date plus the 7-day case fill-rate trend.

    Args:
        dc_id: Optional DC code. Empty means all DCs.
        ship_date: YYYY-MM-DD, "today", "tomorrow" (default, the orders being picked now) or "yesterday".

    Returns:
        Orders by status, lines/cases ordered vs picked vs short, case fill rate, and daily fill
        rate for the previous 7 ship dates.
    """
    d = parse_date(ship_date)
    p = {"ship_date": d}
    status = db.query(f"""
        SELECT o.status, COUNT(*) AS orders, SUM(o.total_cases) AS cases
        FROM {{outbound_orders}} o WHERE o.ship_date = :ship_date{dc_clause(dc_id, 'o', p)}
        GROUP BY o.status ORDER BY o.status""", p)
    lines = db.query(f"""
        SELECT COUNT(*) AS lines, SUM(l.qty_ordered) AS cases_ordered, SUM(l.qty_picked) AS cases_picked,
               SUM(l.qty_short) AS cases_short,
               SUM(CASE WHEN l.qty_short > 0 THEN 1 ELSE 0 END) AS short_lines
        FROM {{order_lines}} l JOIN {{outbound_orders}} o ON o.order_id = l.order_id
        WHERE o.ship_date = :ship_date{dc_clause(dc_id, 'o', p)}""", p)[0]
    tp = {"d0": as_of() - timedelta(days=7), "d1": as_of()}
    trend = db.query(f"""
        SELECT o.ship_date, SUM(l.qty_ordered) AS ordered, SUM(l.qty_picked) AS shipped
        FROM {{order_lines}} l JOIN {{outbound_orders}} o ON o.order_id = l.order_id
        WHERE o.ship_date > :d0 AND o.ship_date <= :d1{dc_clause(dc_id, 'o', tp)}
        GROUP BY o.ship_date ORDER BY o.ship_date""", tp)
    for t in trend:
        t["case_fill_rate_pct"] = pct(t["shipped"], t["ordered"])
    done = (lines["cases_picked"] or 0) + (lines["cases_short"] or 0)
    return ok(ship_date=d.isoformat(), dc_id=dc_id.upper() or "ALL", orders_by_status=status, lines=lines,
              pick_progress_pct=pct(done, lines["cases_ordered"]),
              fill_rate_on_completed_pct=pct(lines["cases_picked"], done),
              fill_rate_trend=trend)


def get_wave_progress(dc_id: str, ship_date: str = "tomorrow") -> dict:
    """Progress of each pick wave against its cutoff, with a projected finish time.

    Projection uses the wave's observed pick rate since release (or the standard rate when the
    wave has not started) and flags waves projected to miss cutoff.

    Args:
        dc_id: DC code (required).
        ship_date: YYYY-MM-DD, "today" or "tomorrow" (default).

    Returns:
        Waves with tasks, cases picked/remaining, % complete, pickers active, cutoff,
        projected finish and AT_RISK flag.
    """
    if not dc_id:
        return error("dc_id is required.")
    d = parse_date(ship_date)
    p = {"ship_date": d}
    rows = db.query(f"""
        SELECT w.wave_id, w.status, w.released_at, w.cutoff_at, w.order_count,
               COUNT(t.task_id) AS tasks,
               SUM(CASE WHEN t.status IN ('COMPLETE', 'SHORT') THEN 1 ELSE 0 END) AS tasks_done,
               SUM(t.qty) AS cases_total,
               SUM(CASE WHEN t.status IN ('COMPLETE', 'SHORT') THEN t.qty ELSE 0 END) AS cases_done,
               COUNT(DISTINCT t.associate_id) AS pickers_assigned
        FROM {{waves}} w LEFT JOIN {{pick_tasks}} t ON t.wave_id = w.wave_id
        WHERE w.ship_date = :ship_date{dc_clause(dc_id, 'w', p)}
        GROUP BY w.wave_id, w.status, w.released_at, w.cutoff_at, w.order_count
        ORDER BY w.cutoff_at, w.wave_id""", p)
    clock = now()
    for r in rows:
        remaining = (r["cases_total"] or 0) - (r["cases_done"] or 0)
        r["cases_remaining"] = remaining
        r["pct_complete"] = pct(r["cases_done"], r["cases_total"])
        released = parse_dt(r["released_at"])
        cutoff = parse_dt(r["cutoff_at"])
        elapsed_h = (clock - released).total_seconds() / 3600 if released and released < clock else 0
        rate = r["cases_done"] / elapsed_h if elapsed_h > 0.25 and r["cases_done"] else None
        if remaining <= 0:
            finish = clock
        else:
            crew = max(1, r["pickers_assigned"] or 0)
            finish = clock + timedelta(hours=remaining / (rate or DEFAULT_PICK_RATE * crew))
        r["observed_rate_cases_per_hr"] = r1(rate) if rate else None
        r["projected_finish"] = finish.strftime("%Y-%m-%d %H:%M")
        r["slack_minutes"] = int((cutoff - finish).total_seconds() / 60) if cutoff else None
        r["at_risk"] = bool(cutoff and finish > cutoff)
    return ok(dc_id=dc_id.upper(), ship_date=d.isoformat(), waves=rows,
              waves_at_risk=[r["wave_id"] for r in rows if r["at_risk"]])


def get_short_picks(dc_id: str = "", days: int = 7, limit: int = 15) -> dict:
    """Top shorted SKUs with reason codes and current stock, to separate true stockouts from
    replenishment or inventory-accuracy failures.

    Args:
        dc_id: Optional DC code. Empty means all DCs.
        days: Look-back window in ship dates (default 7).
        limit: Max SKUs to return (default 15).

    Returns:
        Shorted SKUs with short cases, lines, dominant reason, and current available cases.
    """
    p = {"d0": as_of() - timedelta(days=int(days)), "d1": as_of() + timedelta(days=1)}
    rows = db.query(f"""
        SELECT l.dc_id, l.sku, i.description, l.short_reason, COUNT(*) AS short_lines, SUM(l.qty_short) AS short_cases,
               SUM(l.qty_short * i.unit_cost) AS lost_sales_cost_usd
        FROM {{order_lines}} l
        JOIN {{outbound_orders}} o ON o.order_id = l.order_id
        JOIN {{items}} i ON i.sku = l.sku
        WHERE l.qty_short > 0 AND o.ship_date > :d0 AND o.ship_date <= :d1{dc_clause(dc_id, 'l', p)}
        GROUP BY l.dc_id, l.sku, i.description, l.short_reason""", p)
    agg: dict = {}
    for r in rows:
        k = (r["dc_id"], r["sku"])
        a = agg.setdefault(k, {"dc_id": r["dc_id"], "sku": r["sku"], "description": r["description"],
                               "short_lines": 0, "short_cases": 0, "lost_sales_cost_usd": 0.0, "reasons": {}})
        a["short_lines"] += r["short_lines"]
        a["short_cases"] += r["short_cases"]
        a["lost_sales_cost_usd"] += r["lost_sales_cost_usd"]
        a["reasons"][r["short_reason"]] = a["reasons"].get(r["short_reason"], 0) + r["short_cases"]
    top = sorted(agg.values(), key=lambda a: -a["short_cases"])[: int(limit)]
    reasons_total: dict = {}
    for a in agg.values():
        for k, v in a["reasons"].items():
            reasons_total[k] = reasons_total.get(k, 0) + v
    if top:
        sp: dict = {}
        keys = ", ".join(f":s{i}" for i in range(len(top)))
        for i, a in enumerate(top):
            sp[f"s{i}"] = a["sku"]
        stock = db.query(f"""SELECT dc_id, sku, SUM(qty_on_hand - qty_allocated) AS available
                             FROM {{inventory}} WHERE status = 'AVAILABLE' AND sku IN ({keys})
                             GROUP BY dc_id, sku""", sp)
        smap = {(s["dc_id"], s["sku"]): s["available"] for s in stock}
        for a in top:
            a["lost_sales_cost_usd"] = round(a["lost_sales_cost_usd"], 2)
            a["available_now"] = smap.get((a["dc_id"], a["sku"]), 0)
            a["dominant_reason"] = max(a["reasons"], key=a["reasons"].get)
            a["diagnosis"] = ("Stock exists now: replenishment timing or inventory accuracy issue"
                              if a["available_now"] > 0 else "No stock: purchasing / inbound issue")
    return ok(lookback_days=int(days), short_cases_by_reason=reasons_total, top_shorted_skus=top)


def recommend_wave_release(dc_id: str, ship_date: str = "tomorrow", pickers_available: int = 0) -> dict:
    """Recommend the order to release / staff the not-yet-complete waves so routes make departure.

    Each open wave gets required picker-hours (remaining cases / standard rate) and the night-shift
    crew hours available before its cutoff (18:00-02:30 window). Waves are sequenced earliest-deadline-first (the first trailers out get picked first).

    Args:
        dc_id: DC code (required).
        ship_date: YYYY-MM-DD, "today" or "tomorrow" (default).
        pickers_available: Pickers you can put on these waves now. 0 = use tonight's scheduled night pickers.

    Returns:
        Sequenced waves with required hours, hours to cutoff, minimum pickers needed and a
        feasibility verdict for the crew available.
    """
    if not dc_id:
        return error("dc_id is required.")
    progress = get_wave_progress(dc_id, ship_date)
    if progress["status"] != "success":
        return progress
    if not pickers_available:
        p = {"work_date": parse_date(ship_date) - timedelta(days=1)}
        roster = db.query(f"""
            SELECT COUNT(*) AS n FROM {{labor_schedule}} s JOIN {{associates}} a ON a.associate_id = s.associate_id
            WHERE s.work_date = :work_date AND s.status = 'SCHEDULED' AND a.role = 'PICKER'
                  AND s.shift = 'NIGHT'{dc_clause(dc_id, 's', p)}""", p)
        pickers_available = roster[0]["n"] if roster else 0
    clock = now()
    work_date = parse_date(ship_date) - timedelta(days=1)
    night_start, night_end = SHIFT_WINDOWS["NIGHT"]
    crew_start = max(clock, datetime.combine(work_date, night_start))
    crew_end = datetime.combine(work_date + timedelta(days=1), night_end)
    open_waves = [w for w in progress["waves"] if w["cases_remaining"] > 0]
    plan, cumulative = [], 0.0
    for w in open_waves:
        cutoff = parse_dt(w["cutoff_at"])
        req = w["cases_remaining"] / DEFAULT_PICK_RATE
        # Crew hours usable before this wave's cutoff: the night shift window, capped at the cutoff.
        hours_left = max(0.0, (min(cutoff, crew_end) - crew_start).total_seconds() / 3600) if cutoff else None
        w_plan = {"wave_id": w["wave_id"], "status": w["status"], "cutoff_at": w["cutoff_at"],
                  "cases_remaining": w["cases_remaining"], "required_picker_hours": r1(req),
                  "crew_hours_before_cutoff": r1(hours_left)}
        plan.append(w_plan)
    plan.sort(key=lambda x: (x["cutoff_at"] or "", x["wave_id"]))
    for i, w in enumerate(plan, start=1):
        cumulative += w["required_picker_hours"]
        hrs = w["crew_hours_before_cutoff"] or 0
        w["sequence"] = i
        w["min_pickers_needed"] = int(-(-cumulative // hrs)) if hrs else None
        w["feasible_with_crew"] = bool(hrs and w["min_pickers_needed"] <= pickers_available)
    return ok(dc_id=dc_id.upper(), ship_date=progress["ship_date"], pickers_available=pickers_available,
              total_required_picker_hours=r1(sum(w["required_picker_hours"] for w in plan)),
              sequence=plan,
              crew_window=f"{crew_start:%Y-%m-%d %H:%M} to {crew_end:%Y-%m-%d %H:%M}",
              note="min_pickers_needed is cumulative: night-shift pickers needed to finish this wave and every wave "
                   "before it by this wave's cutoff (or the end of the night shift, whichever is first).")


def lookup_order(order_id: str = "", customer_keyword: str = "") -> dict:
    """Find an order by id, or the latest orders for a customer name / chain keyword.

    Args:
        order_id: Exact order id (e.g. OMTX0000123).
        customer_keyword: Part of a customer or chain name (e.g. "Burger Barn #4312") when the id is unknown.

    Returns:
        Order header(s) with status, route, wave and ship date; line detail when a single order is found.
    """
    p: dict = {}
    if order_id:
        p["oid"] = order_id.strip().upper()
        where = "o.order_id = :oid"
    elif customer_keyword:
        p["kw"] = f"%{customer_keyword.strip().lower()}%"
        where = "(LOWER(c.customer_name) LIKE :kw OR LOWER(c.chain) LIKE :kw)"
    else:
        return error("Provide order_id or customer_keyword.")
    orders = db.query(f"""
        SELECT o.order_id, o.dc_id, c.customer_name, o.route_id, o.ship_date, o.status, o.wave_id,
               o.total_lines, o.total_cases, o.priority
        FROM {{outbound_orders}} o JOIN {{customers}} c ON c.customer_id = o.customer_id
        WHERE {where}
        ORDER BY o.ship_date DESC, o.order_id
        LIMIT 10""", p)
    result = {"orders": orders}
    if len(orders) == 1 or order_id:
        if orders:
            lp = {"oid": orders[0]["order_id"]}
            result["lines"] = db.query("""
                SELECT l.line_number, l.sku, i.description, i.temp_zone, l.qty_ordered, l.qty_picked, l.qty_short,
                       l.short_reason
                FROM {order_lines} l JOIN {items} i ON i.sku = l.sku
                WHERE l.order_id = :oid ORDER BY l.line_number""", lp)
    return ok(**result)


def diagnose_zone_backlog(dc_id: str, zone: str, ship_date: str = "tomorrow") -> dict:
    """Explain why a zone is behind ("Why are we behind in the cooler?") and what to do about it.

    Compares the zone's remaining cases with its recent pick rate and crew, and checks for empty pick
    faces blocking open picks, shorts, and pickers working outside their home zone.

    Args:
        dc_id: DC code (required).
        zone: DRY, COOLER or FREEZER, or an aisle code such as D03 / C01.
        ship_date: YYYY-MM-DD or "tomorrow" (default, the work being picked now).

    Returns:
        Zone status (remaining cases, rate over the last 2 hours, active pickers, hours to finish vs
        hours to cutoff) and ranked likely causes, each with evidence and a corrective action.
    """
    if not dc_id or not zone:
        return error("dc_id and zone are required.")
    z = zone.strip().upper()
    is_temp = z in ("DRY", "COOLER", "FREEZER")
    d = parse_date(ship_date)
    clock = now()
    p = {"ship_date": d, "z": z if is_temp else f"%-{z}-%"}
    t0 = clock - timedelta(hours=2)
    zone_sql = "l.zone = :z" if is_temp else "t.location_id LIKE :z"
    tasks = db.query(f"""
        SELECT t.task_id, t.sku, t.location_id, t.qty, t.qty_picked, t.status, t.associate_id, t.completed_at,
               w.cutoff_at, a.home_zone
        FROM {{pick_tasks}} t
        JOIN {{waves}} w ON w.wave_id = t.wave_id
        JOIN {{locations}} l ON l.location_id = t.location_id
        LEFT JOIN {{associates}} a ON a.associate_id = t.associate_id
        WHERE w.ship_date = :ship_date AND {zone_sql}{dc_clause(dc_id, 't', p)}""", p)
    if not tasks:
        return ok(dc_id=dc_id.upper(), zone=z, note="No pick work found for this zone and ship date.")
    open_t = [t for t in tasks if t["status"] not in ("COMPLETE", "SHORT")]
    remaining = sum(t["qty"] for t in open_t)
    recent = [t for t in tasks if t["completed_at"] and parse_dt(t["completed_at"]) >= t0]
    recent_cases = sum(t["qty_picked"] for t in recent)
    rate = recent_cases / 2.0
    active = {t["associate_id"] for t in recent if t["associate_id"]}
    out_of_zone = {t["associate_id"] for t in recent if t["associate_id"] and is_temp and t["home_zone"] != z}
    cutoff = min(parse_dt(t["cutoff_at"]) for t in open_t) if open_t else None
    hours_to_finish = remaining / rate if rate else None
    hours_to_cutoff = (cutoff - clock).total_seconds() / 3600 if cutoff else None

    # Empty / short pick faces that block open tasks.
    locs = sorted({t["location_id"] for t in open_t})
    blockers = []
    if locs:
        lp: dict = {}
        stock = db.query(f"""SELECT location_id, SUM(qty_on_hand) AS on_hand FROM {{inventory}}
                             WHERE status = 'AVAILABLE' AND location_id IN ({in_clause('l', locs, lp)})
                             GROUP BY location_id""", lp)
        smap = {s["location_id"]: s["on_hand"] for s in stock}
        # A face blocks pickers when it can't cover the next open pick from it (faces are refilled
        # during the shift, so compare with the next pick, not the whole night's demand).
        next_pick: dict = {}
        total: dict = {}
        for t in open_t:
            next_pick[t["location_id"]] = min(next_pick.get(t["location_id"], t["qty"]), t["qty"])
            total[t["location_id"]] = total.get(t["location_id"], 0) + t["qty"]
        for loc, q in next_pick.items():
            if smap.get(loc, 0) < q:
                blockers.append({"location_id": loc, "next_pick_cases": q, "open_cases": total[loc],
                                 "on_hand": smap.get(loc, 0)})
        blockers.sort(key=lambda b: -b["open_cases"])
    shorts = [t for t in tasks if t["status"] == "SHORT"]

    causes = []
    if hours_to_finish is None or (hours_to_cutoff is not None and hours_to_finish > hours_to_cutoff):
        causes.append({"cause": "Pick rate too low for remaining work",
                       "evidence": f"{remaining} cases left, {round(rate)} cases/hr over the last 2h with "
                                   f"{len(active)} pickers",
                       "action": "Add pickers to this zone or re-sequence waves so the earliest routes finish first"})
    if blockers:
        causes.append({"cause": "Pick faces can't cover open picks",
                       "evidence": f"{len(blockers)} slots can't cover their next pick, e.g. "
                                   f"{blockers[0]['location_id']} ({blockers[0]['on_hand']} on hand, next pick "
                                   f"{blockers[0]['next_pick_cases']}, {blockers[0]['open_cases']} cases still to pick)",
                       "action": "Run CRITICAL replenishments for these slots before the pickers reach them"})
    if shorts:
        causes.append({"cause": "Short picks on this ship date",
                       "evidence": f"{len(shorts)} tasks shorted",
                       "action": "Check whether stock is in reserve or on an inbound trailer at the dock"})
    if out_of_zone:
        causes.append({"cause": "Pickers working outside their home zone",
                       "evidence": f"{len(out_of_zone)} of {len(active)} active pickers are cross-zone",
                       "action": "Cross-zone pickers run slower (equipment, PPE, unfamiliar slots); swap back if possible"})
    if not causes:
        causes.append({"cause": "Zone is on pace", "evidence": "projected finish is before cutoff",
                       "action": "No action needed; recheck in an hour"})
    return ok(dc_id=dc_id.upper(), zone=z, ship_date=d.isoformat(), remaining_cases=remaining,
              open_tasks=len(open_t), cases_per_hour_last_2h=r1(rate), active_pickers=len(active),
              hours_to_finish=r1(hours_to_finish) if hours_to_finish else None,
              hours_to_cutoff=r1(hours_to_cutoff) if hours_to_cutoff is not None else None,
              likely_causes=causes, blocking_slots=blockers[:10])
