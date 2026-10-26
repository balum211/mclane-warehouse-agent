"""Slotting tools: velocity vs travel analysis and re-slot (swap) recommendations."""

from __future__ import annotations

from datetime import datetime, timedelta

from .. import db
from .common import TRAVEL_FT_PER_SEC, as_of, dc_clause, error, ok, pct, r1

HEAVY_LB = 35.0


def _velocity(dc_id: str, days: int) -> list[dict]:
    p = {"t0": datetime.combine(as_of() - timedelta(days=days), datetime.min.time())}
    return db.query(f"""
        SELECT s.sku, i.description, i.case_weight_lb, l.zone, s.location_id, l.level, l.distance_to_dock_ft,
               l.is_golden_zone,
               COUNT(t.task_id) AS picks, COALESCE(SUM(t.qty_picked), 0) AS cases
        FROM {{slot_assignments}} s
        JOIN {{locations}} l ON l.location_id = s.location_id
        JOIN {{items}} i ON i.sku = s.sku
        LEFT JOIN {{pick_tasks}} t ON t.location_id = s.location_id AND t.sku = s.sku
             AND t.completed_at >= :t0
        WHERE 1 = 1{dc_clause(dc_id, 's', p)}
        GROUP BY s.sku, i.description, i.case_weight_lb, l.zone, s.location_id, l.level, l.distance_to_dock_ft,
                 l.is_golden_zone""", p)


def analyze_slotting(dc_id: str, temp_zone: str = "", top_n: int = 10, days: int = 14) -> dict:
    """Compare pick velocity with slot travel distance and recommend re-slot swaps.

    Ranks SKUs by picks over the look-back window and pick faces by distance to the dock. In an
    ideal layout the k-th fastest SKU sits in the k-th closest face. Fast movers in far slots are
    paired with slow movers occupying close (golden-zone) slots in the same temperature zone.

    Args:
        dc_id: DC code (required).
        temp_zone: Optional DRY, COOLER or FREEZER. Empty analyzes all zones.
        top_n: Number of swap recommendations to return (default 10).
        days: Velocity look-back window in days (default 14).

    Returns:
        Slotting efficiency % per zone (ideal travel / current travel), recommended swaps with
        weekly travel feet and labor hours saved, and the total opportunity.
    """
    if not dc_id:
        return error("dc_id is required.")
    rows = _velocity(dc_id, int(days))
    zones = sorted({r["zone"] for r in rows if not temp_zone or r["zone"] == temp_zone.upper()})
    weeks = int(days) / 7.0
    summary, swaps = [], []
    for zone in zones:
        zr = [r for r in rows if r["zone"] == zone]
        by_vel = sorted(zr, key=lambda r: -r["picks"])
        dists = sorted(r["distance_to_dock_ft"] for r in zr)
        current = sum(r["picks"] * r["distance_to_dock_ft"] * 2 for r in zr)
        ideal = sum(r["picks"] * d * 2 for r, d in zip(by_vel, dists))
        summary.append({"zone": zone, "skus": len(zr), "picks": sum(r["picks"] for r in zr),
                        "slotting_efficiency_pct": pct(ideal, current),
                        "weekly_excess_travel_ft": round((current - ideal) / weeks)})
        n = max(1, len(zr) // 5)  # "fast" = top 20% by picks; "close" = 20% nearest faces
        close_cut = dists[n - 1]
        fast_far = [r for r in by_vel[:n] if r["distance_to_dock_ft"] > close_cut]
        slow_close = sorted([r for r in by_vel[n:] if r["distance_to_dock_ft"] <= close_cut],
                            key=lambda r: r["picks"])
        for a, b in zip(fast_far, slow_close):
            saved_ft = (a["picks"] - b["picks"]) * (a["distance_to_dock_ft"] - b["distance_to_dock_ft"]) * 2 / weeks
            if saved_ft <= 0:
                continue
            swaps.append({
                "zone": zone,
                "move_fast_sku": a["sku"], "fast_description": a["description"], "fast_weekly_picks": r1(a["picks"] / weeks),
                "from_location": a["location_id"], "from_distance_ft": a["distance_to_dock_ft"],
                "swap_with_slow_sku": b["sku"], "slow_description": b["description"],
                "slow_weekly_picks": r1(b["picks"] / weeks),
                "to_location": b["location_id"], "to_distance_ft": b["distance_to_dock_ft"],
                "to_golden_zone": bool(b["is_golden_zone"]),
                "weekly_travel_saved_ft": round(saved_ft),
                "weekly_labor_hours_saved": round(saved_ft / TRAVEL_FT_PER_SEC / 3600, 2),
            })
    swaps.sort(key=lambda s: -s["weekly_travel_saved_ft"])
    top = swaps[: int(top_n)]
    # Ergonomics: heavy, frequently picked cases should sit at floor level, not on the upper pick level.
    ergo = sorted([{"sku": r["sku"], "description": r["description"], "case_weight_lb": r["case_weight_lb"],
                    "location_id": r["location_id"], "level": r["level"], "weekly_picks": r1(r["picks"] / weeks)}
                   for r in rows if r["case_weight_lb"] >= HEAVY_LB and r["level"] >= 2 and r["picks"] > 0
                   and (not temp_zone or r["zone"] == temp_zone.upper())],
                  key=lambda x: -x["weekly_picks"])[:10]
    return ok(dc_id=dc_id.upper(), lookback_days=int(days), zones=summary,
              recommended_swaps=top,
              total_weekly_hours_saved_top_swaps=round(sum(s["weekly_labor_hours_saved"] for s in top), 1),
              total_swap_candidates=len(swaps),
              ergonomic_flags=ergo,
              method="Swap = exchange pick faces of a top-20% velocity SKU in a far slot and a slow SKU in a "
                     "near slot, same temp zone. Savings use round-trip distance at 4 ft/s.")


def get_slot_utilization(dc_id: str) -> dict:
    """Location occupancy and cube (case capacity) utilization by zone and location type.

    Args:
        dc_id: DC code (required).

    Returns:
        Per zone and PICK/RESERVE: locations, occupied locations, occupancy %, cases on hand,
        case capacity and utilization %.
    """
    if not dc_id:
        return error("dc_id is required.")
    p: dict = {}
    rows = db.query(f"""
        SELECT l.zone, l.location_type, COUNT(*) AS locations,
               SUM(CASE WHEN x.cases > 0 THEN 1 ELSE 0 END) AS occupied,
               SUM(COALESCE(x.cases, 0)) AS cases_on_hand,
               SUM(l.capacity_cases) AS capacity_cases
        FROM {{locations}} l
        LEFT JOIN (SELECT location_id, SUM(qty_on_hand) AS cases FROM {{inventory}} GROUP BY location_id) x
             ON x.location_id = l.location_id
        WHERE 1 = 1{dc_clause(dc_id, 'l', p)}
        GROUP BY l.zone, l.location_type
        ORDER BY l.zone, l.location_type""", p)
    for r in rows:
        r["occupancy_pct"] = pct(r["occupied"], r["locations"])
        r["cube_utilization_pct"] = pct(r["cases_on_hand"], r["capacity_cases"])
    return ok(dc_id=dc_id.upper(), utilization=rows)


def get_sku_affinity(dc_id: str, sku: str = "", top_n: int = 10, days: int = 7) -> dict:
    """SKU pairs that are frequently ordered together, to slot them near each other (shorter pick paths).

    Args:
        dc_id: DC code (required).
        sku: Optional SKU to find partners for. Empty returns the strongest pairs among the 80 most
            frequently ordered SKUs.
        top_n: Pairs to return (default 10).
        days: Look-back in ship dates (default 7).

    Returns:
        Pairs with co-occurrence count, lift (how much more often than chance), each SKU's location and
        the distance between their pick faces. High lift + far apart = co-location opportunity.
    """
    if not dc_id:
        return error("dc_id is required.")
    p = {"d0": as_of() - timedelta(days=int(days)), "d1": as_of()}
    lines = db.query(f"""
        SELECT l.order_id, l.sku FROM {{order_lines}} l JOIN {{outbound_orders}} o ON o.order_id = l.order_id
        WHERE o.ship_date > :d0 AND o.ship_date <= :d1{dc_clause(dc_id, 'l', p)}""", p)
    orders: dict = {}
    freq: dict = {}
    for ln in lines:
        orders.setdefault(ln["order_id"], set()).add(ln["sku"])
        freq[ln["sku"]] = freq.get(ln["sku"], 0) + 1
    universe = {sku} if sku else set(sorted(freq, key=lambda k: -freq[k])[:80])
    pairs: dict = {}
    for skus in orders.values():
        anchors = skus & universe
        for a in anchors:
            for b in skus:
                if a == b or (not sku and b not in universe) or (not sku and b < a):
                    continue
                pairs[(a, b)] = pairs.get((a, b), 0) + 1
    n = len(orders) or 1
    scored = []
    for (a, b), c in pairs.items():
        if c < 5:
            continue
        lift = c * n / (freq[a] * freq[b])
        scored.append((lift, c, a, b))
    scored.sort(reverse=True)
    top = scored[: int(top_n)]
    keys = sorted({x for t in top for x in (t[2], t[3])})
    sp: dict = {}
    slots = {}
    if keys:
        ph = ", ".join(f":k{i}" for i in range(len(keys)))
        for i, k in enumerate(keys):
            sp[f"k{i}"] = k
        for r in db.query(f"""SELECT s.sku, s.location_id, l.zone, l.aisle, l.bay, l.distance_to_dock_ft, i.description
                               FROM {{slot_assignments}} s JOIN {{locations}} l ON l.location_id = s.location_id
                               JOIN {{items}} i ON i.sku = s.sku
                               WHERE s.sku IN ({ph}){dc_clause(dc_id, 's', sp)}""", sp):
            slots[r["sku"]] = r
    out = []
    for lift, c, a, b in top:
        sa, sb = slots.get(a, {}), slots.get(b, {})
        same_aisle = sa.get("aisle") == sb.get("aisle")
        gap = abs(sa.get("bay", 0) - sb.get("bay", 0)) * 9 if same_aisle else \
            abs(sa.get("distance_to_dock_ft", 0) - sb.get("distance_to_dock_ft", 0)) + 30
        out.append({"sku_a": a, "description_a": sa.get("description"), "location_a": sa.get("location_id"),
                    "sku_b": b, "description_b": sb.get("description"), "location_b": sb.get("location_id"),
                    "orders_together": c, "lift": round(lift, 2), "approx_walk_between_ft": round(gap),
                    "co_locate": gap > 60 and sa.get("zone") == sb.get("zone")})
    return ok(dc_id=dc_id.upper(), orders_analyzed=len(orders), pairs=out)
