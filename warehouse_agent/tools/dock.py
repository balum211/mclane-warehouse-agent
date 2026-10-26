"""Dock and yard tools: appointment schedule, exceptions, door recommendations, utilization."""

from __future__ import annotations

from datetime import datetime, time, timedelta

from .. import db
from .common import dc_clause, error, now, ok, parse_date, parse_dt, pct

LATE_MINUTES = 30
WAIT_MINUTES = 60


def _appointments(dc_id: str, day, direction: str = "") -> list[dict]:
    start = datetime.combine(day, time(0, 0))
    p = {"t0": start, "t1": start + timedelta(days=1)}
    dir_sql = ""
    if direction:
        p["direction"] = direction.upper()
        dir_sql = " AND a.direction = :direction"
    return db.query(f"""
        SELECT a.appointment_id, a.dc_id, a.door_id, d.temp_capable, a.direction, a.carrier, a.reference_id,
               a.temp_zone, a.scheduled_start, a.scheduled_end, a.actual_arrival, a.door_assigned_at,
               a.completed_at, a.status
        FROM {{dock_appointments}} a JOIN {{dock_doors}} d ON d.door_id = a.door_id
        WHERE a.scheduled_start >= :t0 AND a.scheduled_start < :t1{dc_clause(dc_id, 'a', p)}{dir_sql}
        ORDER BY a.scheduled_start, a.door_id""", p)


def get_dock_schedule(dc_id: str, day: str = "today", direction: str = "") -> dict:
    """Dock appointments for a day with status counts.

    Args:
        dc_id: DC code (required).
        day: YYYY-MM-DD, "today" (default), "tomorrow" or "yesterday".
        direction: Optional INBOUND or OUTBOUND.

    Returns:
        Status counts and the appointment list (door, carrier, ASN/route, temp zone, times).
    """
    if not dc_id:
        return error("dc_id is required.")
    d = parse_date(day)
    rows = _appointments(dc_id, d, direction)
    counts: dict = {}
    for r in rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    return ok(dc_id=dc_id.upper(), day=d.isoformat(), counts=counts, appointments=rows)


def get_dock_exceptions(dc_id: str = "", day: str = "today") -> dict:
    """Detect dock problems: late carriers, trailers waiting for a door, no-shows, double-booked
    doors and cold-chain loads on non-refrigerated doors.

    Args:
        dc_id: Optional DC code. Empty checks every DC.
        day: YYYY-MM-DD or "today" (default).

    Returns:
        Exceptions grouped by type, each with the appointment, door, carrier and minutes late/waiting.
    """
    d = parse_date(day)
    rows = _appointments(dc_id, d)
    clock = now()
    late, waiting, no_show, temp, clash = [], [], [], [], []
    for r in rows:
        s, arr = parse_dt(r["scheduled_start"]), parse_dt(r["actual_arrival"])
        base = {k: r[k] for k in ("appointment_id", "dc_id", "door_id", "direction", "carrier", "reference_id",
                                  "temp_zone", "scheduled_start", "status")}
        if arr and (arr - s).total_seconds() / 60 > LATE_MINUTES:
            late.append({**base, "minutes_late": int((arr - s).total_seconds() / 60)})
        if r["status"] == "CHECKED_IN" and arr and not r["door_assigned_at"]:
            wait = int((clock - arr).total_seconds() / 60)
            if wait > WAIT_MINUTES:
                waiting.append({**base, "minutes_waiting": wait,
                                "detention_risk": wait > 120, "actual_arrival": r["actual_arrival"]})
        if r["status"] in ("NO_SHOW",) or (r["status"] == "SCHEDULED" and s < clock - timedelta(minutes=60)):
            no_show.append(base)
        if r["temp_zone"] in ("COOLER", "FREEZER") and not r["temp_capable"] and r["status"] != "COMPLETED":
            temp.append({**base, "issue": f"{r['temp_zone']} load assigned to non-refrigerated door"})
    active = [r for r in rows if r["status"] not in ("COMPLETED", "NO_SHOW")]
    for i, a in enumerate(active):
        for b in active[i + 1:]:
            if a["door_id"] == b["door_id"] and parse_dt(a["scheduled_start"]) < parse_dt(b["scheduled_end"]) \
                    and parse_dt(b["scheduled_start"]) < parse_dt(a["scheduled_end"]):
                clash.append({"door_id": a["door_id"], "dc_id": a["dc_id"],
                              "appointments": [a["appointment_id"], b["appointment_id"]],
                              "window": f"{a['scheduled_start']} / {b['scheduled_start']}"})
    return ok(day=d.isoformat(), dc_id=dc_id.upper() or "ALL",
              summary={"late_arrivals": len(late), "waiting_for_door": len(waiting), "no_shows": len(no_show),
                       "temp_mismatches": len(temp), "door_conflicts": len(clash)},
              waiting_for_door=waiting, temp_mismatches=temp, door_conflicts=clash, late_arrivals=late,
              no_shows=no_show)


def recommend_door(dc_id: str, appointment_id: str) -> dict:
    """Recommend dock doors for an appointment: right direction, refrigerated when the load needs it,
    and free for the appointment window (or from now if the trailer is already on the yard).

    Args:
        dc_id: DC code (required).
        appointment_id: Appointment to place (e.g. from get_dock_exceptions).

    Returns:
        The appointment and up to 5 candidate doors with the reason each fits.
    """
    if not dc_id or not appointment_id:
        return error("dc_id and appointment_id are required.")
    p = {"appt": appointment_id.strip().upper()}
    appt = db.query("SELECT * FROM {dock_appointments} WHERE appointment_id = :appt", p)
    if not appt:
        return error(f"Appointment {appointment_id} not found.")
    a = appt[0]
    s, e = parse_dt(a["scheduled_start"]), parse_dt(a["scheduled_end"])
    clock = now()
    if a["status"] == "CHECKED_IN":
        e = clock + (e - s)
        s = clock
    dp: dict = {"dir": a["direction"]}
    doors = db.query(f"SELECT door_id, temp_capable FROM {{dock_doors}} WHERE door_type = :dir"
                     f"{dc_clause(dc_id, '', dp)} ORDER BY door_id", dp)
    busy = _appointments(dc_id, s.date())
    need_temp = a["temp_zone"] in ("COOLER", "FREEZER")
    out = []
    for d in doors:
        if need_temp and not d["temp_capable"]:
            continue
        conflicts = [b for b in busy if b["door_id"] == d["door_id"] and b["appointment_id"] != a["appointment_id"]
                     and b["status"] not in ("COMPLETED", "NO_SHOW")
                     and parse_dt(b["scheduled_start"]) < e and s < parse_dt(b["scheduled_end"])]
        if conflicts:
            continue
        out.append({"door_id": d["door_id"], "temp_capable": bool(d["temp_capable"]),
                    "reason": ("refrigerated, " if d["temp_capable"] else "") + f"free {s:%H:%M}-{e:%H:%M}"})
    # Prefer non-refrigerated doors for dry loads so reefer doors stay open for cold chain.
    out.sort(key=lambda x: (x["temp_capable"] != need_temp, x["door_id"]))
    return ok(appointment=a, window=f"{s:%Y-%m-%d %H:%M} to {e:%H:%M}", candidate_doors=out[:5],
              note=None if out else "No compatible door free in the window; consider yard staging or rescheduling.")


def get_door_utilization(dc_id: str, day: str = "today") -> dict:
    """Booked hours per dock door versus a 20-hour operating window.

    Args:
        dc_id: DC code (required).
        day: YYYY-MM-DD or "today" (default).

    Returns:
        Per door booked hours and utilization %, plus averages for inbound and outbound doors.
    """
    if not dc_id:
        return error("dc_id is required.")
    d = parse_date(day)
    rows = _appointments(dc_id, d)
    dp: dict = {}
    doors = db.query(f"SELECT door_id, door_type, temp_capable FROM {{dock_doors}} WHERE 1 = 1"
                     f"{dc_clause(dc_id, '', dp)} ORDER BY door_id", dp)
    booked: dict = {}
    for r in rows:
        if r["status"] == "NO_SHOW":
            continue
        h = (parse_dt(r["scheduled_end"]) - parse_dt(r["scheduled_start"])).total_seconds() / 3600
        booked[r["door_id"]] = booked.get(r["door_id"], 0.0) + h
    out = [{"door_id": x["door_id"], "door_type": x["door_type"], "temp_capable": bool(x["temp_capable"]),
            "booked_hours": round(booked.get(x["door_id"], 0.0), 1),
            "utilization_pct": pct(booked.get(x["door_id"], 0.0), 20)} for x in doors]
    avg = {}
    for t in ("INBOUND", "OUTBOUND"):
        sel = [o["utilization_pct"] or 0 for o in out if o["door_type"] == t]
        avg[t] = round(sum(sel) / len(sel), 1) if sel else None
    return ok(dc_id=dc_id.upper(), day=d.isoformat(), average_utilization_pct=avg, doors=out)


def predict_dock_arrivals(dc_id: str, day: str = "today") -> dict:
    """Predict arrival times for appointments that have not arrived yet, from each carrier's history.

    Uses the carrier's median minutes late across recent inbound appointments (network-wide, so small
    carriers still get a prediction) and the share of arrivals within 30 minutes of the slot. A
    Vertex AI forecasting model can replace this baseline in the pilot.

    Args:
        dc_id: DC code (required).
        day: YYYY-MM-DD or "today" (default).

    Returns:
        Pending appointments with scheduled time, predicted arrival, predicted minutes late, carrier
        on-time %, and a flag when the predicted arrival collides with the next booking on the door.
    """
    if not dc_id:
        return error("dc_id is required.")
    d = parse_date(day)
    hist = db.query("""
        SELECT carrier, scheduled_start, actual_arrival FROM {dock_appointments}
        WHERE direction = 'INBOUND' AND actual_arrival IS NOT NULL""")
    by_carrier: dict = {}
    for h in hist:
        late = (parse_dt(h["actual_arrival"]) - parse_dt(h["scheduled_start"])).total_seconds() / 60
        by_carrier.setdefault(h["carrier"], []).append(late)
    rows = _appointments(dc_id, d, "INBOUND")
    clock = now()
    out = []
    for r in rows:
        if r["actual_arrival"] or r["status"] in ("COMPLETED", "NO_SHOW"):
            continue
        lates = sorted(by_carrier.get(r["carrier"], [0.0]))
        median = lates[len(lates) // 2]
        on_time = pct(sum(1 for x in lates if x <= LATE_MINUTES), len(lates))
        s = parse_dt(r["scheduled_start"])
        pred = max(s + timedelta(minutes=median), clock)
        nxt = [b for b in rows if b["door_id"] == r["door_id"] and parse_dt(b["scheduled_start"]) > s
               and b["appointment_id"] != r["appointment_id"]]
        collision = bool(nxt and pred + (parse_dt(r["scheduled_end"]) - s) > parse_dt(nxt[0]["scheduled_start"]))
        out.append({"appointment_id": r["appointment_id"], "carrier": r["carrier"], "door_id": r["door_id"],
                    "temp_zone": r["temp_zone"], "scheduled_start": r["scheduled_start"],
                    "predicted_arrival": pred.strftime("%Y-%m-%d %H:%M"),
                    "predicted_minutes_late": int((pred - s).total_seconds() / 60),
                    "carrier_on_time_pct": on_time, "carrier_history_n": len(lates),
                    "door_collision_risk": collision})
    return ok(dc_id=dc_id.upper(), day=d.isoformat(), pending=len(out), predictions=out,
              method="Baseline: carrier median lateness from appointment history.")


def assess_inbound_impact(dc_id: str, day: str = "today") -> dict:
    """Find inbound trailers that are late, waiting or not yet received whose freight is needed for
    tomorrow's orders, so they can be prioritized at the dock and cross-docked to pick faces.

    Args:
        dc_id: DC code (required).
        day: YYYY-MM-DD or "today" (default).

    Returns:
        Per open inbound appointment: status, minutes late/waiting, and the ASN SKUs where tomorrow's
        open demand exceeds available stock (cases at risk, orders affected). Sorted by impact.
    """
    if not dc_id:
        return error("dc_id is required.")
    d = parse_date(day)
    rows = [r for r in _appointments(dc_id, d, "INBOUND") if r["status"] in ("SCHEDULED", "CHECKED_IN", "AT_DOOR")]
    if not rows:
        return ok(dc_id=dc_id.upper(), day=d.isoformat(), trailers=[])
    p: dict = {}
    asn_keys = ", ".join(f":a{i}" for i in range(len(rows)))
    for i, r in enumerate(rows):
        p[f"a{i}"] = r["reference_id"]
    lines = db.query(f"""
        SELECT l.asn_id, l.sku, i.description, l.cases_expected, l.cases_received
        FROM {{asn_lines}} l JOIN {{items}} i ON i.sku = l.sku
        WHERE l.asn_id IN ({asn_keys})""", p)
    dp = {"ship_date": d + timedelta(days=1)}
    demand = {x["sku"]: x for x in db.query(f"""
        SELECT l.sku, SUM(l.qty_ordered - l.qty_picked) AS open_cases, COUNT(DISTINCT l.order_id) AS orders
        FROM {{order_lines}} l JOIN {{outbound_orders}} o ON o.order_id = l.order_id
        WHERE o.ship_date = :ship_date AND o.status NOT IN ('SHIPPED', 'CANCELLED'){dc_clause(dc_id, 'o', dp)}
        GROUP BY l.sku""", dp)}
    sp: dict = {}
    stock = {x["sku"]: x["available"] for x in db.query(f"""
        SELECT sku, SUM(qty_on_hand) AS available FROM {{inventory}}
        WHERE status = 'AVAILABLE'{dc_clause(dc_id, '', sp)} GROUP BY sku""", sp)}
    clock = now()
    out = []
    for r in rows:
        crit = []
        for ln in (x for x in lines if x["asn_id"] == r["reference_id"]):
            dem = demand.get(ln["sku"])
            if not dem:
                continue
            gap = dem["open_cases"] - stock.get(ln["sku"], 0)
            if gap > 0:
                crit.append({"sku": ln["sku"], "description": ln["description"], "cases_on_trailer":
                             ln["cases_expected"] - ln["cases_received"], "open_demand": dem["open_cases"],
                             "available_now": stock.get(ln["sku"], 0), "cases_at_risk": gap,
                             "orders_affected": dem["orders"]})
        s, arr = parse_dt(r["scheduled_start"]), parse_dt(r["actual_arrival"])
        out.append({"appointment_id": r["appointment_id"], "asn_id": r["reference_id"], "carrier": r["carrier"],
                    "status": r["status"], "door_id": r["door_id"], "temp_zone": r["temp_zone"],
                    "minutes_late": int((arr - s).total_seconds() / 60) if arr else
                    max(0, int((clock - s).total_seconds() / 60)),
                    "minutes_waiting": int((clock - arr).total_seconds() / 60) if arr and r["status"] == "CHECKED_IN"
                    else None,
                    "critical_skus": crit, "cases_at_risk": sum(c["cases_at_risk"] for c in crit),
                    "orders_affected": sum(c["orders_affected"] for c in crit)})
    out.sort(key=lambda x: -x["cases_at_risk"])
    return ok(dc_id=dc_id.upper(), day=d.isoformat(), trailers=out,
              recommendation="Door the trailers with cases_at_risk first, receive critical SKUs first and putaway "
                             "them straight to pick faces (cross-dock) ahead of tonight's waves.")
