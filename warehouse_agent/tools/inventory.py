"""Inventory tools: positions, expiry (FEFO), replenishment, stockout risk, cycle counts."""

from __future__ import annotations

from datetime import timedelta

from .. import db
from .common import as_of, dc_clause, error, in_clause, ok, parse_date, r1


def get_inventory_position(sku_or_keyword: str, dc_id: str = "") -> dict:
    """Look up on-hand, allocated and available cases for a SKU or item keyword, by DC.

    Args:
        sku_or_keyword: Exact SKU (e.g. "100123") or a word from the description (e.g. "fries", "cola").
        dc_id: Optional DC code (MTX, MGA, MCA, MNY, FDL, FOH). Empty means all DCs.

    Returns:
        Per DC and SKU: on_hand, allocated, available, blocked (hold/damaged/QC), average daily
        demand over the last 7 days and days of supply.
    """
    if not sku_or_keyword:
        return error("Provide a SKU or keyword.")
    p = {"q": sku_or_keyword.strip(), "kw": f"%{sku_or_keyword.strip().lower()}%"}
    rows = db.query(f"""
        SELECT i.sku, i.description, i.temp_zone, i.unit_cost, v.dc_id,
               SUM(v.qty_on_hand) AS on_hand,
               SUM(v.qty_allocated) AS allocated,
               SUM(CASE WHEN v.status = 'AVAILABLE' THEN v.qty_on_hand - v.qty_allocated ELSE 0 END) AS available,
               SUM(CASE WHEN v.status <> 'AVAILABLE' THEN v.qty_on_hand ELSE 0 END) AS blocked,
               COUNT(*) AS inventory_records
        FROM {{inventory}} v JOIN {{items}} i ON i.sku = v.sku
        WHERE (i.sku = :q OR LOWER(i.description) LIKE :kw){dc_clause(dc_id, 'v', p)}
        GROUP BY i.sku, i.description, i.temp_zone, i.unit_cost, v.dc_id
        ORDER BY i.sku, v.dc_id
        LIMIT 40""", p)
    if not rows:
        return ok(results=[], note=f"No inventory found for '{sku_or_keyword}'.")
    d1 = as_of()
    dp = {"d0": d1 - timedelta(days=7), "d1": d1}
    skus = sorted({r["sku"] for r in rows})
    demand = db.query(f"""
        SELECT l.dc_id, l.sku, SUM(l.qty_ordered) AS cases
        FROM {{order_lines}} l JOIN {{outbound_orders}} o ON o.order_id = l.order_id
        WHERE o.ship_date > :d0 AND o.ship_date <= :d1 AND l.sku IN ({in_clause('s', skus, dp)})
        GROUP BY l.dc_id, l.sku""", dp)
    dmap = {(d["dc_id"], d["sku"]): d["cases"] / 7.0 for d in demand}
    for r in rows:
        avg = dmap.get((r["dc_id"], r["sku"]), 0.0)
        r["avg_daily_demand"] = r1(avg)
        r["days_of_supply"] = r1(r["available"] / avg) if avg else None
        r["available_value_usd"] = round(r["available"] * r["unit_cost"], 2)
    return ok(results=rows)


def get_expiring_inventory(dc_id: str = "", days_ahead: int = 3, temp_zone: str = "") -> dict:
    """Find lots that are expired or expire within `days_ahead` days (FEFO / shrink risk).

    Args:
        dc_id: Optional DC code. Empty means all DCs.
        days_ahead: Look-ahead window in days (default 3).
        temp_zone: Optional DRY, COOLER or FREEZER filter.

    Returns:
        Lots sorted by expiry with cases, value at cost, days left and a recommended action.
    """
    p = {"limit_date": as_of() + timedelta(days=int(days_ahead))}
    zone = ""
    if temp_zone:
        p["zone"] = temp_zone.upper()
        zone = " AND i.temp_zone = :zone"
    rows = db.query(f"""
        SELECT v.dc_id, v.sku, i.description, i.temp_zone, v.location_id, v.lot_number, v.expiry_date,
               v.qty_on_hand, v.qty_allocated, v.status, i.unit_cost
        FROM {{inventory}} v JOIN {{items}} i ON i.sku = v.sku
        WHERE v.expiry_date IS NOT NULL AND v.expiry_date <= :limit_date AND v.qty_on_hand > 0
              {dc_clause(dc_id, 'v', p)}{zone}
        ORDER BY v.expiry_date, v.dc_id
        LIMIT 200""", p)
    total_value = 0.0
    for r in rows:
        days_left = (parse_date(r["expiry_date"]) - as_of()).days
        r["days_left"] = days_left
        r["value_usd"] = round(r["qty_on_hand"] * r.pop("unit_cost"), 2)
        total_value += r["value_usd"]
        if days_left < 0:
            r["recommended_action"] = "Expired: place on HOLD, pull from pick face, dispose or return to vendor"
        elif days_left <= 1:
            r["recommended_action"] = "Pick first (FEFO) on tonight's waves or offer to nearby customers at markdown"
        else:
            r["recommended_action"] = "Force FEFO allocation; confirm newer lots are not being picked first"
    return ok(lot_count=len(rows), total_value_usd=round(total_value, 2), lots=rows[:60],
              truncated=len(rows) > 60)


def get_replenishment_needs(dc_id: str, limit: int = 25) -> dict:
    """Pick faces below their min that need a replenishment move from reserve (FEFO lot chosen).

    Args:
        dc_id: DC code (required).
        limit: Max pick faces to return (default 25), most urgent first.

    Returns:
        Pick faces with face qty, open allocation, min/max, the reserve location and lot to pull,
        cases to move, and urgency (CRITICAL = in-flight picks will short without it).
    """
    if not dc_id:
        return error("dc_id is required.")
    p: dict = {}
    faces = db.query(f"""
        SELECT s.dc_id, s.location_id, s.sku, i.description, i.temp_zone, s.min_qty, s.max_qty,
               COALESCE(SUM(v.qty_on_hand), 0) AS face_qty,
               COALESCE(SUM(v.qty_allocated), 0) AS face_allocated
        FROM {{slot_assignments}} s
        JOIN {{items}} i ON i.sku = s.sku
        LEFT JOIN {{inventory}} v ON v.location_id = s.location_id AND v.sku = s.sku AND v.status = 'AVAILABLE'
        WHERE 1 = 1{dc_clause(dc_id, 's', p)}
        GROUP BY s.dc_id, s.location_id, s.sku, i.description, i.temp_zone, s.min_qty, s.max_qty""", p)
    reserve = db.query(f"""
        SELECT v.sku, v.location_id, v.lot_number, v.qty_on_hand, v.expiry_date, v.received_date
        FROM {{inventory}} v JOIN {{locations}} l ON l.location_id = v.location_id
        WHERE l.location_type = 'RESERVE' AND v.status = 'AVAILABLE' AND v.qty_on_hand > 0
              {dc_clause(dc_id, 'v', p)}""", p)
    by_sku: dict[str, list] = {}
    for r in reserve:
        by_sku.setdefault(r["sku"], []).append(r)
    needs = []
    for f in faces:
        net = f["face_qty"] - f["face_allocated"]
        if f["face_qty"] >= f["min_qty"] and net >= 0:
            continue
        lots = sorted(by_sku.get(f["sku"], []), key=lambda x: (x["expiry_date"] or "9999", x["received_date"]))
        move = f["max_qty"] - f["face_qty"]
        src = lots[0] if lots else None
        f["urgency"] = "CRITICAL" if net < 0 else ("HIGH" if f["face_qty"] == 0 else "NORMAL")
        f["cases_to_move"] = min(move, src["qty_on_hand"]) if src else 0
        f["from_location"] = src["location_id"] if src else None
        f["from_lot"] = src["lot_number"] if src else None
        f["reserve_cases_total"] = sum(x["qty_on_hand"] for x in lots)
        if not src:
            f["note"] = "No reserve stock: true stockout risk, check inbound ASNs / buyer"
        needs.append(f)
    order = {"CRITICAL": 0, "HIGH": 1, "NORMAL": 2}
    needs.sort(key=lambda x: (order[x["urgency"]], x["face_qty"] - x["min_qty"]))
    return ok(dc_id=dc_id.upper(), faces_needing_replenishment=len(needs),
              critical=sum(1 for n in needs if n["urgency"] == "CRITICAL"),
              no_reserve=sum(1 for n in needs if not n["from_location"]),
              tasks=needs[: int(limit)])


def get_stockout_risk(dc_id: str = "", ship_date: str = "tomorrow") -> dict:
    """SKUs whose available inventory (pick face + reserve) can't cover open order demand for a ship date.

    Args:
        dc_id: Optional DC code. Empty means all DCs.
        ship_date: YYYY-MM-DD, "today" or "tomorrow" (default).

    Returns:
        SKUs with open demand, available cases, shortfall and affected customer orders.
    """
    d = parse_date(ship_date)
    p = {"ship_date": d}
    demand = db.query(f"""
        SELECT l.dc_id, l.sku, i.description, SUM(l.qty_ordered - l.qty_picked) AS open_cases,
               COUNT(DISTINCT l.order_id) AS orders
        FROM {{order_lines}} l
        JOIN {{outbound_orders}} o ON o.order_id = l.order_id
        JOIN {{items}} i ON i.sku = l.sku
        WHERE o.ship_date = :ship_date AND o.status NOT IN ('SHIPPED', 'CANCELLED'){dc_clause(dc_id, 'l', p)}
        GROUP BY l.dc_id, l.sku, i.description""", p)
    sp: dict = {}
    stock = db.query(f"""
        SELECT dc_id, sku, SUM(qty_on_hand) AS available
        FROM {{inventory}} WHERE status = 'AVAILABLE'{dc_clause(dc_id, '', sp)}
        GROUP BY dc_id, sku""", sp)
    smap = {(s["dc_id"], s["sku"]): s["available"] for s in stock}
    risks = []
    for r in demand:
        avail = smap.get((r["dc_id"], r["sku"]), 0)
        if r["open_cases"] > avail:
            r["available"] = avail
            r["shortfall_cases"] = r["open_cases"] - avail
            risks.append(r)
    risks.sort(key=lambda x: -x["shortfall_cases"])
    return ok(ship_date=d.isoformat(), skus_at_risk=len(risks), risks=risks[:40])


def get_cycle_count_variances(dc_id: str = "", days: int = 7) -> dict:
    """Summarize cycle count accuracy and the SKUs/locations driving variance.

    Args:
        dc_id: Optional DC code. Empty means all DCs.
        days: Look-back window in days (default 7).

    Returns:
        Inventory record accuracy %, net and absolute variance value, and the worst offenders
        (repeat variances suggest a process problem such as mis-picks or unrecorded damages).
    """
    p = {"d0": as_of() - timedelta(days=int(days))}
    rows = db.query(f"""
        SELECT c.dc_id, c.sku, i.description, c.location_id,
               COUNT(*) AS counts,
               SUM(CASE WHEN c.variance_qty <> 0 THEN 1 ELSE 0 END) AS counts_with_variance,
               SUM(c.variance_qty) AS net_variance_cases,
               SUM(c.variance_value) AS net_variance_usd,
               SUM(CASE WHEN c.variance_value < 0 THEN -c.variance_value ELSE c.variance_value END) AS abs_variance_usd
        FROM {{cycle_counts}} c JOIN {{items}} i ON i.sku = c.sku
        WHERE c.count_date >= :d0{dc_clause(dc_id, 'c', p)}
        GROUP BY c.dc_id, c.sku, i.description, c.location_id""", p)
    total = sum(r["counts"] for r in rows)
    bad = sum(r["counts_with_variance"] for r in rows)
    rows.sort(key=lambda r: -r["abs_variance_usd"])
    for r in rows:
        r["net_variance_usd"] = round(r["net_variance_usd"], 2)
        r["abs_variance_usd"] = round(r["abs_variance_usd"], 2)
    return ok(counts=total, accuracy_pct=round(100.0 * (total - bad) / total, 1) if total else None,
              net_variance_usd=round(sum(r["net_variance_usd"] for r in rows), 2),
              abs_variance_usd=round(sum(r["abs_variance_usd"] for r in rows), 2),
              repeat_offenders=[r for r in rows if r["counts_with_variance"] >= 2][:10],
              top_variances=rows[:10])


def detect_inventory_anomalies(dc_id: str) -> dict:
    """Scan inventory records for integrity problems and rank locations for priority cycle counts.

    Checks: negative on-hand, allocation greater than on-hand, expired product still AVAILABLE,
    quantity above slot capacity, chilled/frozen product stored in an ambient (DRY) location, and
    HOLD/DAMAGED stock older than 7 days. Temperature-zone and expiry violations are food-safety
    issues and rank first.

    Args:
        dc_id: DC code (required).

    Returns:
        Anomalies with type, severity, location, SKU, evidence and a recommended action, plus a
        prioritized cycle-count list.
    """
    if not dc_id:
        return error("dc_id is required.")
    p = {"today": as_of(), "stale": as_of() - timedelta(days=7)}
    rows = db.query(f"""
        SELECT v.inventory_id, v.location_id, v.sku, i.description, i.temp_zone AS item_zone, l.zone AS location_zone,
               l.capacity_cases, v.qty_on_hand, v.qty_allocated, v.status, v.expiry_date, v.received_date, i.unit_cost
        FROM {{inventory}} v
        JOIN {{items}} i ON i.sku = v.sku
        JOIN {{locations}} l ON l.location_id = v.location_id
        WHERE (v.qty_on_hand < 0
               OR v.qty_allocated > v.qty_on_hand
               OR (v.expiry_date IS NOT NULL AND v.expiry_date < :today AND v.status = 'AVAILABLE' AND v.qty_on_hand > 0)
               OR v.qty_on_hand > l.capacity_cases
               OR i.temp_zone <> l.zone
               OR (v.status IN ('HOLD', 'DAMAGED') AND v.received_date < :stale))
              {dc_clause(dc_id, 'v', p)}""", p)
    found = []
    for r in rows:
        ev = {"location_id": r["location_id"], "sku": r["sku"], "description": r["description"],
              "qty_on_hand": r["qty_on_hand"]}
        if r["item_zone"] != r["location_zone"]:
            found.append({**ev, "type": "TEMP_ZONE_VIOLATION", "severity": "CRITICAL",
                          "evidence": f"{r['item_zone']} item stored in {r['location_zone']} location",
                          "action": "Move to correct zone now; QA to assess product temperature and hold if abused"})
        if r["expiry_date"] and str(r["expiry_date"]) < as_of().isoformat() and r["status"] == "AVAILABLE" \
                and r["qty_on_hand"] > 0:
            found.append({**ev, "type": "EXPIRED_AVAILABLE", "severity": "CRITICAL",
                          "evidence": f"expired {r['expiry_date']} but still AVAILABLE",
                          "action": "Set status HOLD so it cannot be allocated; pull and dispose / RTV"})
        if r["qty_on_hand"] < 0:
            found.append({**ev, "type": "NEGATIVE_ON_HAND", "severity": "HIGH",
                          "evidence": "negative on-hand (unconfirmed pick or missed receipt)",
                          "action": "Count the location and the adjacent slots; reconcile last picks"})
        elif r["qty_allocated"] > r["qty_on_hand"]:
            found.append({**ev, "type": "OVER_ALLOCATED", "severity": "HIGH",
                          "evidence": f"allocated {r['qty_allocated']} > on hand {r['qty_on_hand']}",
                          "action": "Replenish before the wave reaches this slot or re-allocate from reserve"})
        if r["qty_on_hand"] > r["capacity_cases"]:
            found.append({**ev, "type": "OVER_CAPACITY", "severity": "MEDIUM",
                          "evidence": f"{r['qty_on_hand']} cases in a {r['capacity_cases']}-case slot",
                          "action": "Likely a receiving/putaway keying error: count and correct"})
        if r["status"] in ("HOLD", "DAMAGED") and str(r["received_date"]) < (as_of() - timedelta(days=7)).isoformat():
            found.append({**ev, "type": "STALE_HOLD", "severity": "LOW",
                          "evidence": f"{r['status']} since before {(as_of() - timedelta(days=7)).isoformat()}",
                          "action": "Disposition the hold (release, RTV or dispose) to free space"})
    sev = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    found.sort(key=lambda a: sev[a["severity"]])
    counts: dict = {}
    for a in found:
        counts[a["type"]] = counts.get(a["type"], 0) + 1
    seen, count_list = set(), []
    for a in found:
        if a["severity"] in ("CRITICAL", "HIGH", "MEDIUM") and a["location_id"] not in seen:
            seen.add(a["location_id"])
            count_list.append({"priority": len(count_list) + 1, "location_id": a["location_id"], "sku": a["sku"],
                               "reason": a["type"]})
    return ok(dc_id=dc_id.upper(), anomaly_counts=counts, anomalies=found[:40],
              priority_cycle_counts=count_list[:15])
