"""Labor tools: productivity vs engineered standards, labor requirement forecast, rosters."""

from __future__ import annotations

from datetime import datetime, timedelta

from .. import db
from .common import (SHIFT_WINDOWS, UTILIZATION, as_of, dc_clause, error, now, ok,
                                          parse_date, pct, r1)


def _standards() -> dict:
    return {(s["role"], s["zone"]): s["engineered_rate"]
            for s in db.query("SELECT role, zone, engineered_rate FROM {labor_standards}")}


def get_labor_productivity(dc_id: str, days: int = 7, role: str = "PICKER") -> dict:
    """Associate productivity against engineered labor standards (performance %).

    Performance % = earned hours / direct hours, where earned hours = cases / engineered rate for the
    role and zone. 100% means working exactly at standard.

    Args:
        dc_id: DC code (required).
        days: Look-back window in days (default 7).
        role: PICKER (default), LOADER, RECEIVER or FORKLIFT.

    Returns:
        DC average performance and cases/hour, utilization (direct share of paid hours), the top and
        bottom performers, and associates under 85% (coaching candidates; new hires flagged).
    """
    if not dc_id:
        return error("dc_id is required.")
    p = {"d0": as_of() - timedelta(days=int(days)), "d1": as_of(), "role": role.upper()}
    rows = db.query(f"""
        SELECT a.associate_id, a.associate_name, a.shift, a.home_zone, a.hire_date, la.zone,
               SUM(la.cases_handled) AS cases, SUM(la.direct_hours) AS direct_hours,
               SUM(la.indirect_hours) AS indirect_hours, COUNT(DISTINCT la.work_date) AS days_worked
        FROM {{labor_activity}} la JOIN {{associates}} a ON a.associate_id = la.associate_id
        WHERE la.work_date >= :d0 AND la.work_date <= :d1 AND la.role = :role{dc_clause(dc_id, 'la', p)}
        GROUP BY a.associate_id, a.associate_name, a.shift, a.home_zone, a.hire_date, la.zone""", p)
    std = _standards()
    people: dict = {}
    for r in rows:
        a = people.setdefault(r["associate_id"], {
            "associate_id": r["associate_id"], "name": r["associate_name"], "shift": r["shift"],
            "home_zone": r["home_zone"], "hire_date": r["hire_date"], "cases": 0, "direct_hours": 0.0,
            "indirect_hours": 0.0, "earned_hours": 0.0, "days_worked": 0})
        a["cases"] += r["cases"]
        a["direct_hours"] += r["direct_hours"]
        a["indirect_hours"] += r["indirect_hours"]
        a["earned_hours"] += r["cases"] / std.get((role.upper(), r["zone"]), 150.0)
        a["days_worked"] = max(a["days_worked"], r["days_worked"])
    out = []
    for a in people.values():
        a["cases_per_hour"] = r1(a["cases"] / a["direct_hours"]) if a["direct_hours"] else None
        a["performance_pct"] = pct(a["earned_hours"], a["direct_hours"])
        a["new_hire"] = (as_of() - parse_date(a["hire_date"])).days < 90
        for k in ("direct_hours", "indirect_hours", "earned_hours"):
            a[k] = r1(a[k])
        out.append(a)
    out.sort(key=lambda a: -(a["performance_pct"] or 0))
    direct = sum(a["direct_hours"] for a in out)
    earned = sum(a["earned_hours"] for a in out)
    indirect = sum(a["indirect_hours"] for a in out)
    return ok(dc_id=dc_id.upper(), role=role.upper(), lookback_days=int(days), associates=len(out),
              avg_performance_pct=pct(earned, direct),
              avg_cases_per_hour=r1(sum(a["cases"] for a in out) / direct) if direct else None,
              direct_utilization_pct=pct(direct, direct + indirect),
              top_performers=out[:5], bottom_performers=out[-5:][::-1],
              below_85_pct=[{"associate_id": a["associate_id"], "name": a["name"],
                             "performance_pct": a["performance_pct"], "new_hire": a["new_hire"]}
                            for a in out if (a["performance_pct"] or 0) < 85])


def forecast_labor_requirement(dc_id: str, ship_date: str = "tomorrow") -> dict:
    """Picker hours needed to finish a ship date's open work vs hours scheduled, by temp zone.

    Required hours = remaining cases / (engineered rate x the DC's recent performance). Available hours =
    scheduled pickers (excluding PTO and call-outs) x remaining shift hours x 85% utilization, for the
    remaining day shift and tonight's night shift.

    Args:
        dc_id: DC code (required).
        ship_date: YYYY-MM-DD, "today" or "tomorrow" (default, picked today/tonight).

    Returns:
        Required vs available hours by zone, the gap in hours and headcount, call-outs, and
        candidates to close the gap (day-shift pickers for overtime, cross-trained roles).
    """
    if not dc_id:
        return error("dc_id is required.")
    d = parse_date(ship_date)
    work_date = d - timedelta(days=1)
    p = {"ship_date": d}
    remaining = db.query(f"""
        SELECT i.temp_zone AS zone, SUM(l.qty_ordered - l.qty_picked - l.qty_short) AS cases
        FROM {{order_lines}} l JOIN {{outbound_orders}} o ON o.order_id = l.order_id JOIN {{items}} i ON i.sku = l.sku
        WHERE o.ship_date = :ship_date AND o.status NOT IN ('SHIPPED', 'LOADED', 'CANCELLED'){dc_clause(dc_id, 'o', p)}
        GROUP BY i.temp_zone""", p)
    perf = get_labor_productivity(dc_id, 7, "PICKER").get("avg_performance_pct") or 95.0
    std = _standards()
    req_by_zone = {r["zone"]: r["cases"] / (std[("PICKER", r["zone"])] * perf / 100.0) for r in remaining}

    sp = {"work_date": work_date}
    roster = db.query(f"""
        SELECT a.associate_id, a.associate_name, a.role, a.home_zone, s.shift, s.status, s.scheduled_hours,
               a.hourly_rate
        FROM {{labor_schedule}} s JOIN {{associates}} a ON a.associate_id = s.associate_id
        WHERE s.work_date = :work_date{dc_clause(dc_id, 's', sp)}""", sp)
    clock = now()
    day_end = datetime.combine(work_date, SHIFT_WINDOWS["DAY"][1])
    day_left = max(0.0, (day_end - clock).total_seconds() / 3600) if clock.date() == work_date else (
        8.0 if clock.date() < work_date else 0.0)
    avail_by_zone: dict = {}
    for r in roster:
        if r["role"] != "PICKER" or r["status"] != "SCHEDULED":
            continue
        hours = r["scheduled_hours"] if r["shift"] == "NIGHT" else min(r["scheduled_hours"], day_left)
        avail_by_zone[r["home_zone"]] = avail_by_zone.get(r["home_zone"], 0.0) + hours * UTILIZATION
    zones = sorted(set(req_by_zone) | set(avail_by_zone))
    by_zone = [{"zone": z, "remaining_cases": next((r["cases"] for r in remaining if r["zone"] == z), 0),
                "required_hours": r1(req_by_zone.get(z, 0)), "available_hours": r1(avail_by_zone.get(z, 0)),
                "gap_hours": r1(avail_by_zone.get(z, 0) - req_by_zone.get(z, 0))} for z in zones]
    required, available = sum(req_by_zone.values()), sum(avail_by_zone.values())
    gap = available - required
    callouts = [r for r in roster if r["status"] == "CALLOUT"]
    candidates = []
    if gap < 0:
        for r in roster:
            if r["status"] != "SCHEDULED":
                continue
            if r["role"] == "PICKER" and r["shift"] == "DAY":
                candidates.append({"associate_id": r["associate_id"], "name": r["associate_name"],
                                   "option": "Extend day shift / overtime into night waves",
                                   "home_zone": r["home_zone"], "ot_cost_per_hour": round(r["hourly_rate"] * 1.5, 2)})
            elif r["role"] in ("LOADER", "FORKLIFT") and r["shift"] == "NIGHT":
                candidates.append({"associate_id": r["associate_id"], "name": r["associate_name"],
                                   "option": f"Cross-train flex from {r['role']} to picking for first 3 hours",
                                   "home_zone": r["home_zone"], "ot_cost_per_hour": 0.0})
    return ok(dc_id=dc_id.upper(), ship_date=d.isoformat(), work_date=work_date.isoformat(),
              dc_performance_pct_used=perf, by_zone=by_zone, required_hours=r1(required),
              available_hours=r1(available), gap_hours=r1(gap),
              headcount_gap=round(-gap / (8 * UTILIZATION), 1) if gap < 0 else 0,
              callouts=[{"associate_id": c["associate_id"], "name": c["associate_name"], "role": c["role"],
                         "shift": c["shift"]} for c in callouts],
              gap_closing_candidates=candidates[:10],
              verdict="SHORT" if gap < 0 else ("TIGHT" if gap < 0.1 * required else "OK"))


def get_shift_roster(dc_id: str, work_date: str = "today", shift: str = "") -> dict:
    """Who is scheduled, on PTO or called out for a date and shift.

    Args:
        dc_id: DC code (required).
        work_date: YYYY-MM-DD, "today" (default) or "tomorrow".
        shift: Optional DAY or NIGHT.

    Returns:
        Counts by role and status plus the roster list.
    """
    if not dc_id:
        return error("dc_id is required.")
    p = {"work_date": parse_date(work_date)}
    shift_sql = ""
    if shift:
        p["shift"] = shift.upper()
        shift_sql = " AND s.shift = :shift"
    rows = db.query(f"""
        SELECT a.associate_id, a.associate_name, a.role, a.home_zone, s.shift, s.status, s.scheduled_hours
        FROM {{labor_schedule}} s JOIN {{associates}} a ON a.associate_id = s.associate_id
        WHERE s.work_date = :work_date{dc_clause(dc_id, 's', p)}{shift_sql}
        ORDER BY s.shift, a.role, a.associate_name""", p)
    counts: dict = {}
    for r in rows:
        k = f"{r['shift']}/{r['role']}/{r['status']}"
        counts[k] = counts.get(k, 0) + 1
    return ok(dc_id=dc_id.upper(), work_date=p["work_date"].isoformat(), counts=counts, roster=rows)
