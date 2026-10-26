"""Cross-WMS tools: landscape, integration health, field mapping, KPI comparison across platforms."""

from __future__ import annotations

from datetime import timedelta

from .. import db
from .common import as_of, dc_clause, now, ok, parse_dt, pct


def get_wms_landscape() -> dict:
    """Which WMS platform (Manhattan Active, Blue Yonder, Argent) runs each DC, with segment and size.

    Returns:
        DCs with wms_system, segment (RETAIL/RESTAURANT), location, square feet, SKU count and associates.
    """
    rows = db.query("""
        SELECT d.dc_id, d.dc_name, d.city, d.state, d.segment, d.wms_system, d.square_feet,
               (SELECT COUNT(*) FROM {slot_assignments} s WHERE s.dc_id = d.dc_id) AS slotted_skus,
               (SELECT COUNT(*) FROM {associates} a WHERE a.dc_id = d.dc_id) AS associates
        FROM {distribution_centers} d ORDER BY d.wms_system, d.dc_id""")
    return ok(distribution_centers=rows,
              note="One canonical schema harmonizes all three WMS platforms; see lookup_field_mapping.")


def get_integration_health(source_system: str = "", dc_id: str = "", hours: int = 24) -> dict:
    """Interface health between the WMS platforms and the host/ERP: error rate, top errors, spikes.

    Args:
        source_system: Optional MANHATTAN_ACTIVE, BLUE_YONDER or ARGENT.
        dc_id: Optional DC code.
        hours: Look-back window in hours (default 24).

    Returns:
        Message and error counts by system/interface, top error codes with sample detail, and hourly
        spikes where the error rate exceeded 25%.
    """
    clock = now()
    p = {"t0": clock - timedelta(hours=int(hours)), "t1": clock}
    sys_sql = ""
    if source_system:
        p["sys"] = source_system.upper()
        sys_sql = " AND e.source_system = :sys"
    rows = db.query(f"""
        SELECT e.dc_id, e.source_system, e.interface, e.source_message_type, e.event_time, e.status,
               e.error_code, e.error_detail
        FROM {{wms_integration_events}} e
        WHERE e.event_time >= :t0 AND e.event_time <= :t1{sys_sql}{dc_clause(dc_id, 'e', p)}""", p)
    by_iface: dict = {}
    errors: dict = {}
    hourly: dict = {}
    for r in rows:
        k = (r["source_system"], r["interface"])
        b = by_iface.setdefault(k, {"source_system": k[0], "interface": k[1],
                                    "source_message_type": r["source_message_type"], "messages": 0, "errors": 0})
        b["messages"] += 1
        hk = (r["dc_id"], r["interface"], parse_dt(r["event_time"]).strftime("%Y-%m-%d %H:00"))
        h = hourly.setdefault(hk, [0, 0])
        h[0] += 1
        if r["status"] != "SUCCESS":
            b["errors"] += 1
            h[1] += 1
            ek = (r["source_system"], r["error_code"])
            e = errors.setdefault(ek, {"source_system": ek[0], "error_code": ek[1], "count": 0,
                                       "sample_detail": r["error_detail"], "dcs": set()})
            e["count"] += 1
            e["dcs"].add(r["dc_id"])
    for b in by_iface.values():
        b["error_rate_pct"] = pct(b["errors"], b["messages"])
    top = sorted(errors.values(), key=lambda e: -e["count"])[:10]
    for e in top:
        e["dcs"] = sorted(e["dcs"])
    spikes = [{"dc_id": k[0], "interface": k[1], "hour": k[2], "messages": v[0], "errors": v[1],
               "error_rate_pct": pct(v[1], v[0])}
              for k, v in sorted(hourly.items()) if v[0] >= 3 and v[1] / v[0] > 0.25]
    total = sum(b["messages"] for b in by_iface.values())
    errs = sum(b["errors"] for b in by_iface.values())
    return ok(window_hours=int(hours), messages=total, errors=errs, error_rate_pct=pct(errs, total),
              by_interface=sorted(by_iface.values(), key=lambda b: -(b["error_rate_pct"] or 0)),
              top_errors=top, spikes=spikes[:20])


def lookup_field_mapping(term: str) -> dict:
    """Translate between source-native WMS field names and the canonical model (and back).

    Args:
        term: A source field (e.g. "PRTNUM", "ItemId", "CodeDate") or canonical field/table (e.g. "expiry_date").

    Returns:
        Matching mappings with source system, entity, field, canonical table/field and transform rule.
        Mappings are illustrative and must be validated against each vendor's interface specs.
    """
    p = {"kw": f"%{term.strip().lower()}%"}
    rows = db.query("""
        SELECT source_system, source_entity, source_field, canonical_table, canonical_field, transform_rule
        FROM {wms_field_map}
        WHERE LOWER(source_field) LIKE :kw OR LOWER(canonical_field) LIKE :kw OR LOWER(canonical_table) LIKE :kw
              OR LOWER(source_entity) LIKE :kw
        ORDER BY canonical_table, canonical_field, source_system""", p)
    return ok(mappings=rows)


def compare_dc_kpis(days: int = 7) -> dict:
    """Side-by-side KPI scorecard for every DC, grouped by WMS platform.

    KPIs: case fill rate, picker performance vs standard, inbound on-time arrival, cycle count
    accuracy and integration error rate.

    Args:
        days: Look-back window in days (default 7).

    Returns:
        One row per DC with the five KPIs and its WMS platform, plus platform averages.
    """
    d0, d1 = as_of() - timedelta(days=int(days)), as_of()
    p = {"d0": d0, "d1": d1}
    fill = {r["dc_id"]: pct(r["shipped"], r["ordered"]) for r in db.query("""
        SELECT o.dc_id, SUM(l.qty_ordered) AS ordered, SUM(l.qty_picked) AS shipped
        FROM {order_lines} l JOIN {outbound_orders} o ON o.order_id = l.order_id
        WHERE o.ship_date > :d0 AND o.ship_date <= :d1 GROUP BY o.dc_id""", p)}
    std = {(s["role"], s["zone"]): s["engineered_rate"]
           for s in db.query("SELECT role, zone, engineered_rate FROM {labor_standards}")}
    perf: dict = {}
    for r in db.query("""
        SELECT dc_id, zone, SUM(cases_handled) AS cases, SUM(direct_hours) AS hours
        FROM {labor_activity} WHERE role = 'PICKER' AND work_date > :d0 AND work_date <= :d1
        GROUP BY dc_id, zone""", p):
        e = perf.setdefault(r["dc_id"], [0.0, 0.0])
        e[0] += r["cases"] / std[("PICKER", r["zone"])]
        e[1] += r["hours"]
    tp = {"t0": now() - timedelta(days=int(days)), "t1": now()}
    ontime: dict = {}
    for r in db.query("""
        SELECT dc_id, scheduled_start, actual_arrival FROM {dock_appointments}
        WHERE direction = 'INBOUND' AND actual_arrival IS NOT NULL
              AND scheduled_start >= :t0 AND scheduled_start <= :t1""", tp):
        e = ontime.setdefault(r["dc_id"], [0, 0])
        e[1] += 1
        if (parse_dt(r["actual_arrival"]) - parse_dt(r["scheduled_start"])).total_seconds() <= 30 * 60:
            e[0] += 1
    acc = {r["dc_id"]: pct(r["good"], r["n"]) for r in db.query("""
        SELECT dc_id, COUNT(*) AS n, SUM(CASE WHEN variance_qty = 0 THEN 1 ELSE 0 END) AS good
        FROM {cycle_counts} WHERE count_date > :d0 AND count_date <= :d1 GROUP BY dc_id""", p)}
    integ = {r["dc_id"]: pct(r["errs"], r["n"]) for r in db.query("""
        SELECT dc_id, COUNT(*) AS n, SUM(CASE WHEN status <> 'SUCCESS' THEN 1 ELSE 0 END) AS errs
        FROM {wms_integration_events} WHERE event_time >= :t0 AND event_time <= :t1 GROUP BY dc_id""", tp)}
    dcs = db.query("SELECT dc_id, dc_name, segment, wms_system FROM {distribution_centers} ORDER BY wms_system, dc_id")
    rows = []
    for d in dcs:
        k = d["dc_id"]
        rows.append({**d, "case_fill_rate_pct": fill.get(k),
                     "picker_performance_pct": pct(*perf[k]) if k in perf else None,
                     "inbound_on_time_pct": pct(*ontime[k]) if k in ontime else None,
                     "inventory_accuracy_pct": acc.get(k), "integration_error_rate_pct": integ.get(k)})
    platforms: dict = {}
    for r in rows:
        platforms.setdefault(r["wms_system"], []).append(r)
    kpis = ["case_fill_rate_pct", "picker_performance_pct", "inbound_on_time_pct", "inventory_accuracy_pct",
            "integration_error_rate_pct"]
    plat_avg = []
    for sys, lst in platforms.items():
        row = {"wms_system": sys, "dcs": len(lst)}
        for k in kpis:
            vals = [x[k] for x in lst if x[k] is not None]
            row[k] = round(sum(vals) / len(vals), 1) if vals else None
        plat_avg.append(row)
    return ok(lookback_days=int(days), scorecard=rows, platform_averages=plat_avg)
