"""Yard and delivery tools: geofences, dwell time changes, PC*MILER miles, and Retail vs
Restaurant on-time delivery (OTD), including how tonight's wave risk turns into missed windows."""

from __future__ import annotations

from datetime import datetime, timedelta

from .. import db, pcmiler
from .common import SHIFT_WINDOWS, as_of, dc_clause, error, in_clause, now, ok, parse_date, parse_dt, pct, r1
from .fulfillment import recommend_wave_release

LATE_REASONS = ("LATE_DEPARTURE", "CUSTOMER_DWELL", "TRAFFIC", "ROUTE_PLAN")
DETENTION_MINUTES = 120


def _mins(a, b) -> float:
    return (parse_dt(b) - parse_dt(a)).total_seconds() / 60


def _segment_clause(segment: str, alias: str, p: dict) -> str:
    if not segment:
        return ""
    p["segment"] = segment.strip().upper()
    return f" AND {alias}.segment = :segment"


def _otd(rows: list[dict]) -> dict:
    n = len(rows)
    late = [r for r in rows if not r["on_time"]]
    reasons: dict[str, int] = {}
    for r in late:
        reasons[r["late_reason"] or "UNKNOWN"] = reasons.get(r["late_reason"] or "UNKNOWN", 0) + 1
    return {"stops": n, "on_time": n - len(late), "otd_pct": pct(n - len(late), n),
            "avg_late_minutes": r1(sum(r["late_minutes"] or 0 for r in late) / len(late)) if late else 0.0,
            "late_reasons": dict(sorted(reasons.items(), key=lambda kv: -kv[1]))}


def get_otd_performance(dc_id: str = "", segment: str = "", days: int = 7, group_by: str = "segment") -> dict:
    """On-time delivery (OTD) for Retail and Restaurant customers, this period vs the prior period.

    A stop is on time when the truck enters the customer geofence by the end of the receiving window
    (restaurants: 60 minute window, retail: 120 minutes).

    Args:
        dc_id: DC code, or "" for all DCs.
        segment: RETAIL, RESTAURANT or "" for both.
        days: Ship dates in the current period, ending today (default 7). The prior period has the same length.
        group_by: segment (default), dc, route, chain or customer.

    Returns:
        OTD % per group for the current and prior period with the change in points, late stops by
        reason (LATE_DEPARTURE, CUSTOMER_DWELL, TRAFFIC, ROUTE_PLAN) and average minutes late; worst groups first.
    """
    days = max(1, int(days))
    g = group_by.strip().lower()
    key = {"segment": "segment", "dc": "dc_id", "route": "route_id", "chain": "chain", "customer": "customer_name"}.get(g)
    if not key:
        return error("group_by must be segment, dc, route, chain or customer.")
    end = as_of()
    p = {"d0": end - timedelta(days=2 * days - 1), "d1": end}
    rows = db.query(f"""
        SELECT s.dc_id, s.route_id, s.segment, s.ship_date, s.on_time, s.late_minutes, s.late_reason,
               c.chain, c.customer_name
        FROM {{route_stops}} s JOIN {{customers}} c ON c.customer_id = s.customer_id
        WHERE s.ship_date >= :d0 AND s.ship_date <= :d1 AND s.on_time IS NOT NULL
              {dc_clause(dc_id, 's', p)}{_segment_clause(segment, 's', p)}""", p)
    if not rows:
        return ok(note="No delivered stops for this filter.")
    split = (end - timedelta(days=days - 1)).isoformat()
    cur = [r for r in rows if str(r["ship_date"]) >= split]
    prior = [r for r in rows if str(r["ship_date"]) < split]
    groups: dict[str, dict] = {}
    for label, part in (("current", cur), ("prior", prior)):
        for r in part:
            groups.setdefault(r[key], {"current": [], "prior": []})[label].append(r)
    out = []
    for name, parts in groups.items():
        c, pr = _otd(parts["current"]), _otd(parts["prior"])
        change = round(c["otd_pct"] - pr["otd_pct"], 1) if c["otd_pct"] is not None and pr["otd_pct"] is not None else None
        out.append({g: name, "current": c, "prior_otd_pct": pr["otd_pct"], "change_pts": change})
    out.sort(key=lambda x: (x["current"]["otd_pct"] if x["current"]["otd_pct"] is not None else 101))
    by_segment = {s: _otd([r for r in cur if r["segment"] == s]) for s in ("RETAIL", "RESTAURANT")}
    return ok(dc_id=dc_id.upper() or "ALL", current_period=f"{split} to {end}", prior_period_days=days,
              overall_current=_otd(cur), overall_prior_otd_pct=_otd(prior)["otd_pct"],
              by_segment={k: v for k, v in by_segment.items() if v["stops"]}, groups=out[:12])


def _yard_visits(dc_id: str, t0: datetime) -> list[dict]:
    """Inbound trailer visits from DC yard geofence ENTER / EXIT, joined to the appointment."""
    p = {"t0": t0}
    ev = db.query(f"""
        SELECT e.reference_id, e.event_type, e.event_time, e.asset_id, e.carrier, a.dc_id, a.door_id, a.status,
               a.temp_zone, a.scheduled_start, a.actual_arrival, a.door_assigned_at, a.completed_at
        FROM {{geofence_events}} e JOIN {{dock_appointments}} a ON a.appointment_id = e.reference_id
        WHERE e.site_type = 'DC_YARD' AND e.reference_type = 'APPOINTMENT' AND e.event_time >= :t0
              {dc_clause(dc_id, 'e', p)}""", p)
    visits: dict[str, dict] = {}
    for e in ev:
        v = visits.setdefault(e["reference_id"], {k: e[k] for k in e if k not in ("event_type", "event_time")})
        v["enter" if e["event_type"] == "ENTER" else "exit"] = e["event_time"]
    return [v for v in visits.values() if "enter" in v]


def _avg(rows: list[dict], field: str) -> float:
    vals = [x[field] for x in rows if field in x]
    return sum(vals) / len(vals) if vals else 0.0


def get_dwell_time_changes(dc_id: str = "", scope: str = "all", days: int = 7, min_change_minutes: int = 10) -> dict:
    """Find where dwell time is changing: inbound trailers in the DC yard and McLane trucks at customer stops.

    Inbound yard dwell is gate-in to gate-out from the DC yard geofence, split into gate-to-door wait,
    unload and door-to-gate. Customer dwell is geofence enter to exit at the store or restaurant.

    Args:
        dc_id: DC code, or "" for all DCs.
        scope: inbound (yard, by carrier), customer (stops, by chain) or all (default).
        days: Length of the current period ending now (default 7); compared with the prior period of equal length.
        min_change_minutes: Only flag changes at least this large (default 10).

    Returns:
        Carriers and chains whose average dwell rose or fell versus the prior period, largest increase
        first, with the component that moved and the dollar / OTD exposure hint.
    """
    days = max(1, int(days))
    scope = scope.strip().lower()
    clock = now()
    split = clock - timedelta(days=days)
    result: dict = {"current_period_start": split.strftime("%Y-%m-%d %H:%M")}
    if scope in ("inbound", "all"):
        stats: dict[str, dict] = {}
        for v in _yard_visits(dc_id, clock - timedelta(days=2 * days)):
            if "exit" not in v:
                continue
            per = "current" if parse_dt(v["enter"]) >= split else "prior"
            s = stats.setdefault(f"{v['dc_id']}|{v['carrier']}", {"current": [], "prior": []})
            comp = {"total": _mins(v["enter"], v["exit"])}
            if v.get("actual_arrival") and v.get("door_assigned_at") and v.get("completed_at"):
                comp.update(gate_to_door=_mins(v["actual_arrival"], v["door_assigned_at"]),
                            unload=_mins(v["door_assigned_at"], v["completed_at"]),
                            door_to_gate=_mins(v["completed_at"], v["exit"]))
            s[per].append(comp)
        rows = []
        for k, s in stats.items():
            if len(s["current"]) < 2 or len(s["prior"]) < 2:
                continue
            dc, carrier = k.split("|")
            cur, pri = _avg(s["current"], "total"), _avg(s["prior"], "total")
            moved = {f: r1(_avg(s["current"], f) - _avg(s["prior"], f)) for f in ("gate_to_door", "unload", "door_to_gate")}
            rows.append({"dc_id": dc, "carrier": carrier, "visits_current": len(s["current"]),
                         "avg_dwell_min_current": r1(cur), "avg_dwell_min_prior": r1(pri),
                         "change_min": r1(cur - pri), "change_pct": pct(cur - pri, pri),
                         "component_change_min": moved,
                         "biggest_driver": max(moved, key=lambda f: moved[f])})
        rows.sort(key=lambda x: -x["change_min"])
        result["inbound_yard"] = [x for x in rows if abs(x["change_min"]) >= min_change_minutes][:10]
        result["inbound_note"] = (f"Trailers over {DETENTION_MINUTES} min in the yard usually incur carrier detention "
                                  "charges; rising gate_to_door means door capacity or labor, rising door_to_gate means "
                                  "paperwork / seal / check-out.")
    if scope in ("customer", "all"):
        p = {"d0": (split - timedelta(days=days)).date(), "d1": clock.date()}
        stops = db.query(f"""
            SELECT s.dc_id, s.segment, s.ship_date, s.dwell_minutes, s.standard_dwell_minutes, s.actual_arrival,
                   s.on_time, c.chain
            FROM {{route_stops}} s JOIN {{customers}} c ON c.customer_id = s.customer_id
            WHERE s.dwell_minutes IS NOT NULL AND s.ship_date >= :d0 AND s.ship_date <= :d1
                  {dc_clause(dc_id, 's', p)}""", p)
        stats = {}
        for s in stops:
            per = "current" if parse_dt(s["actual_arrival"]) >= split else "prior"
            stats.setdefault((s["dc_id"], s["segment"], s["chain"]), {"current": [], "prior": []})[per].append(s)
        rows = []
        for (dc, seg, chain), parts in stats.items():
            if len(parts["current"]) < 3 or len(parts["prior"]) < 3:
                continue
            cur = sum(x["dwell_minutes"] for x in parts["current"]) / len(parts["current"])
            pri = sum(x["dwell_minutes"] for x in parts["prior"]) / len(parts["prior"])
            std = sum(x["standard_dwell_minutes"] for x in parts["current"]) / len(parts["current"])
            rows.append({"dc_id": dc, "segment": seg, "chain": chain, "stops_current": len(parts["current"]),
                         "avg_dwell_min_current": r1(cur), "avg_dwell_min_prior": r1(pri),
                         "standard_dwell_min": r1(std), "change_min": r1(cur - pri), "change_pct": pct(cur - pri, pri),
                         "otd_pct_current": pct(sum(x["on_time"] for x in parts["current"]), len(parts["current"]))})
        rows.sort(key=lambda x: -x["change_min"])
        result["customer_stops"] = [x for x in rows if abs(x["change_min"]) >= min_change_minutes][:10]
        result["customer_note"] = ("Extra minutes at one stop push every later stop on the route; restaurant windows "
                                   "are 60 minutes, so 20+ extra minutes of dwell usually costs OTD downstream.")
    if len(result) == 1:
        return error("scope must be inbound, customer or all.")
    return ok(dc_id=dc_id.upper() or "ALL", lookback_days=days, **result)


def get_geofence_activity(dc_id: str, hours: int = 3) -> dict:
    """What telematics geofences show right now: trailers in the DC yard and McLane trucks at customers.

    Flags trailers inside the yard geofence that have not checked in at the gate (early arrivals or
    missed check-ins), trailers in the yard past the detention threshold, and route trucks on site.

    Args:
        dc_id: DC code (required).
        hours: Window for the recent event count (default 3).

    Returns:
        Trailers in the yard with minutes on site and appointment status, flagged exceptions, trucks
        currently inside a customer geofence, and ENTER / EXIT counts for the window.
    """
    if not dc_id:
        return error("dc_id is required.")
    clock = now()
    p = {"t0": clock - timedelta(days=1), "t1": clock}
    ev = db.query(f"""
        SELECT e.event_id, e.site_type, e.site_id, e.asset_id, e.carrier, e.reference_type, e.reference_id,
               e.event_type, e.event_time
        FROM {{geofence_events}} e
        WHERE e.event_time >= :t0 AND e.event_time <= :t1{dc_clause(dc_id, 'e', p)}
        ORDER BY e.event_time""", p)
    inside: dict[tuple, dict] = {}
    for e in ev:
        k = (e["site_id"], e["asset_id"], e["reference_id"])
        if e["event_type"] == "ENTER":
            inside[k] = e
        else:
            inside.pop(k, None)
    yard_refs = [e["reference_id"] for e in inside.values()
                 if e["site_type"] == "DC_YARD" and e["reference_type"] == "APPOINTMENT"]
    appts = {}
    if yard_refs:
        ap: dict = {}
        for a in db.query(f"""
                SELECT appointment_id, door_id, status, temp_zone, scheduled_start, actual_arrival
                FROM {{dock_appointments}} WHERE appointment_id IN ({in_clause('a', yard_refs, ap)})""", ap):
            appts[a["appointment_id"]] = a
    yard, flags, at_customers = [], [], []
    for e in inside.values():
        on_site = r1(_mins(e["event_time"], clock))
        if e["site_type"] == "DC_YARD" and e["reference_type"] == "APPOINTMENT":
            a = appts.get(e["reference_id"], {})
            row = {"asset_id": e["asset_id"], "carrier": e["carrier"], "appointment_id": e["reference_id"],
                   "entered_yard": e["event_time"], "minutes_in_yard": on_site, "appointment_status": a.get("status"),
                   "scheduled_start": a.get("scheduled_start"), "door_id": a.get("door_id"),
                   "temp_zone": a.get("temp_zone")}
            yard.append(row)
            if not a.get("actual_arrival"):
                flags.append({**row, "flag": "IN_YARD_NOT_CHECKED_IN",
                              "action": "Check the trailer in and door it now if a matching door is free"})
            elif a.get("status") == "CHECKED_IN" and on_site > DETENTION_MINUTES:
                flags.append({**row, "flag": "DETENTION_RISK", "action": "Door this trailer next"})
        elif e["site_type"] == "CUSTOMER":
            at_customers.append({"tractor_id": e["asset_id"], "trip_id": e["reference_id"], "customer_id": e["site_id"],
                                 "arrived": e["event_time"], "minutes_on_site": on_site})
    t_recent = clock - timedelta(hours=int(hours))
    recent = [e for e in ev if parse_dt(e["event_time"]) >= t_recent]
    yard.sort(key=lambda x: -x["minutes_in_yard"])
    return ok(dc_id=dc_id.upper(), trailers_in_yard=len(yard), yard=yard[:15], exceptions=flags,
              trucks_at_customers=sorted(at_customers, key=lambda x: -x["minutes_on_site"])[:10],
              events_last_hours={"hours": int(hours), "enter": sum(e["event_type"] == "ENTER" for e in recent),
                                 "exit": sum(e["event_type"] == "EXIT" for e in recent)})


def get_route_status(dc_id: str, ship_date: str = "today", route_id: str = "") -> dict:
    """Live delivery status by route: departures, stops delivered, trucks on site, and stops projected late.

    Args:
        dc_id: DC code (required).
        ship_date: YYYY-MM-DD or "today" (default; trucks on the road now).
        route_id: Optional route, e.g. MTX-R07, for stop-level detail.

    Returns:
        Per route: departure delay, stops done / planned, late so far and projected late (telematics ETA
        after the window end); Retail vs Restaurant projected OTD for the day.
    """
    if not dc_id:
        return error("dc_id is required.")
    d = parse_date(ship_date, as_of())
    p = {"ship_date": d}
    route_sql = ""
    if route_id:
        p["route_id"] = route_id.strip().upper()
        route_sql = " AND s.route_id = :route_id"
    stops = db.query(f"""
        SELECT s.stop_id, s.trip_id, s.route_id, s.stop_seq, s.customer_id, c.customer_name, s.segment, s.window_start,
               s.window_end, s.planned_arrival, s.eta, s.actual_arrival, s.actual_departure, s.dwell_minutes,
               s.on_time, s.late_minutes, s.late_reason, s.status
        FROM {{route_stops}} s JOIN {{customers}} c ON c.customer_id = s.customer_id
        WHERE s.ship_date = :ship_date{dc_clause(dc_id, 's', p)}{route_sql}
        ORDER BY s.route_id, s.stop_seq""", p)
    if not stops:
        return ok(dc_id=dc_id.upper(), ship_date=d.isoformat(), note="No route stops for this date.")
    tp = {"ship_date": d}
    trips = {t["trip_id"]: t for t in db.query(f"""
        SELECT trip_id, route_id, planned_departure, actual_departure, departure_delay_minutes, delay_reason,
               planned_miles, status
        FROM {{route_trips}} WHERE ship_date = :ship_date{dc_clause(dc_id, '', tp)}""", tp)}
    for s in stops:
        late = s["on_time"] == 0
        if s["eta"] and not s["actual_arrival"]:
            late = parse_dt(s["eta"]) > parse_dt(s["window_end"])
        s["late_or_projected_late"] = bool(late)
    routes: dict[str, dict] = {}
    for s in stops:
        t = trips.get(s["trip_id"], {})
        rr = routes.setdefault(s["route_id"], {
            "route_id": s["route_id"], "segment": s["segment"], "trip_status": t.get("status"),
            "planned_departure": t.get("planned_departure"), "departure_delay_min": t.get("departure_delay_minutes"),
            "delay_reason": t.get("delay_reason"), "pcmiler_miles": t.get("planned_miles"),
            "stops_planned": 0, "stops_delivered": 0, "late_so_far": 0, "projected_late": 0})
        rr["stops_planned"] += 1
        rr["stops_delivered"] += s["status"] == "DELIVERED"
        rr["late_so_far"] += s["on_time"] == 0
        rr["projected_late"] += bool(s["eta"] and not s["actual_arrival"] and s["late_or_projected_late"])
    by_seg = {}
    for seg in ("RETAIL", "RESTAURANT"):
        ss = [s for s in stops if s["segment"] == seg]
        if ss:
            by_seg[seg] = {"stops": len(ss), "late_or_projected_late": sum(s["late_or_projected_late"] for s in ss),
                           "projected_otd_pct": pct(sum(not s["late_or_projected_late"] for s in ss), len(ss))}
    out = sorted(routes.values(), key=lambda x: -(x["late_so_far"] + x["projected_late"]))
    result = {"routes": out[:12]}
    if route_id:
        result["stops"] = stops
    return ok(dc_id=dc_id.upper(), ship_date=d.isoformat(), by_segment=by_seg, **result)


def _site(site_id: str) -> dict | None:
    sid = site_id.strip().upper()
    p = {"sid": sid}
    rows = db.query("""SELECT dc_id AS site_id, dc_id, dc_name AS name, latitude, longitude
                       FROM {distribution_centers} WHERE dc_id = :sid""", p)
    if not rows:
        rows = db.query("""SELECT customer_id AS site_id, dc_id, customer_name AS name, latitude, longitude
                           FROM {customers} WHERE customer_id = :sid""", p)
    return rows[0] if rows else None


def lane_miles(origin_id: str, dest_id: str) -> dict:
    """PC*MILER miles for one lane: live API, then the lane_miles table, then an estimate."""
    o, d = _site(origin_id), _site(dest_id)
    if not o or not d:
        return {"error": f"Unknown site {origin_id if not o else dest_id}"}
    try:
        live = pcmiler.pcmiler_route([(o["latitude"], o["longitude"]), (d["latitude"], d["longitude"])])
    except Exception as e:  # noqa: BLE001 - fall back to stored / estimated miles
        live = None
        fallback_reason = f"PC*MILER API call failed: {e}"
    else:
        fallback_reason = None
    if live:
        return {"origin_id": o["site_id"], "dest_id": d["site_id"], **live}
    p = {"o": o["site_id"], "d": d["site_id"]}
    rows = db.query("""SELECT practical_miles, shortest_miles, drive_minutes, source, computed_date
                       FROM {lane_miles} WHERE origin_id = :o AND dest_id = :d""", p)
    if rows:
        out = {"origin_id": o["site_id"], "dest_id": d["site_id"], **rows[0]}
    else:
        out = {"origin_id": o["site_id"], "dest_id": d["site_id"], "source": "ESTIMATE",
               **pcmiler.estimate_lane(o["site_id"], o["latitude"], o["longitude"], d["site_id"], d["latitude"],
                                       d["longitude"])}
    if fallback_reason:
        out["note"] = fallback_reason
    return out


def get_route_miles(dc_id: str, route_id: str = "", customer_id: str = "", ship_date: str = "tomorrow") -> dict:
    """PC*MILER miles and drive time for a customer lane or a route's stop sequence.

    Uses PC*MILER Web Services when PCMILER_API_KEY is configured, otherwise the PC*MILER miles loaded
    in lane_miles (synthetic in the demo), otherwise a labelled estimate.

    Args:
        dc_id: DC code (required).
        route_id: Route such as FDL-R03: returns each leg DC -> stops -> DC for that ship date.
        customer_id: Customer id: returns the DC -> customer lane.
        ship_date: For routes, YYYY-MM-DD, "today" or "tomorrow" (default).

    Returns:
        Practical / shortest miles, drive minutes and source for the lane, or per-leg and total for the route.
    """
    if not dc_id or not (route_id or customer_id):
        return error("dc_id and one of route_id or customer_id are required.")
    dc = dc_id.strip().upper()
    if customer_id:
        lane = lane_miles(dc, customer_id)
        if "error" in lane:
            return error(lane["error"])
        return ok(dc_id=dc, lane=lane)
    d = parse_date(ship_date, as_of())
    p = {"ship_date": d, "route_id": route_id.strip().upper()}
    stops = db.query("""
        SELECT s.stop_seq, s.customer_id, c.customer_name, s.segment, s.window_start, s.window_end, s.planned_arrival
        FROM {route_stops} s JOIN {customers} c ON c.customer_id = s.customer_id
        WHERE s.route_id = :route_id AND s.ship_date = :ship_date ORDER BY s.stop_seq""", p)
    if not stops:
        return error(f"No stops for {p['route_id']} on {d}.")
    seq = [dc] + [s["customer_id"] for s in stops] + [dc]
    legs, total_mi, total_min, sources = [], 0.0, 0, set()
    for a, b in zip(seq, seq[1:]):
        lane = lane_miles(a, b)
        if "error" in lane:
            return error(lane["error"])
        miles = lane.get("practical_miles") or 0.0
        total_mi += miles
        total_min += lane.get("drive_minutes") or 0
        sources.add(lane.get("source"))
        legs.append({"from": a, "to": b, "practical_miles": miles, "drive_minutes": lane.get("drive_minutes")})
    return ok(dc_id=dc, route_id=p["route_id"], ship_date=d.isoformat(), stops=stops, legs=legs,
              total_practical_miles=r1(total_mi), total_drive_hours=r1(total_min / 60), source=sorted(sources))


def lookup_customer_site(customer: str) -> dict:
    """Geolocation, geofence, receiving window, route and recent delivery record for a store or restaurant.

    Args:
        customer: Customer id (e.g. CFDL0042) or part of the name / chain (e.g. "Taco Trail #1234").

    Returns:
        Up to 5 matching sites with latitude / longitude, geofence radius, receiving window, standard dwell,
        servicing DC and route, PC*MILER miles from the DC, and OTD / dwell over the last 7 deliveries.
    """
    if not customer:
        return error("customer is required.")
    p = {"id": customer.strip().upper(), "kw": f"%{customer.strip().lower()}%"}
    sites = db.query("""
        SELECT c.customer_id, c.customer_name, c.chain, c.segment, c.dc_id, c.route_id, c.latitude, c.longitude,
               c.delivery_window_start, c.delivery_window_end, c.standard_dwell_minutes, g.geofence_id, g.radius_m
        FROM {customers} c LEFT JOIN {geofences} g ON g.site_id = c.customer_id
        WHERE c.customer_id = :id OR LOWER(c.customer_name) LIKE :kw
        ORDER BY c.customer_id LIMIT 5""", p)
    if not sites:
        return error(f"No customer matches '{customer}'.")
    for s in sites:
        lane = lane_miles(s["dc_id"], s["customer_id"])
        s["pcmiler_miles_from_dc"] = lane.get("practical_miles")
        s["drive_minutes_from_dc"] = lane.get("drive_minutes")
        s["miles_source"] = lane.get("source")
        hist = db.query("""
            SELECT ship_date, actual_arrival, dwell_minutes, on_time, late_minutes, late_reason FROM {route_stops}
            WHERE customer_id = :cid AND on_time IS NOT NULL ORDER BY ship_date DESC LIMIT 7""",
                        {"cid": s["customer_id"]})
        s["last_deliveries"] = hist
        s["otd_pct_last_7"] = pct(sum(h["on_time"] for h in hist), len(hist))
    return ok(sites=sites)


def assess_route_otd_risk(dc_id: str, ship_date: str = "tomorrow", pickers_available: int = 0) -> dict:
    """Turn wave / labor risk into delivery risk: which trailers leave late and which customer windows miss.

    Projects each open wave's finish with the crew available (earliest-deadline-first), turns minutes past
    the wave cutoff into a late departure for that wave's routes, and checks every planned stop's arrival
    plus the delay against its receiving window. Run it again with more pickers to show the re-plan effect.

    Args:
        dc_id: DC code (required).
        ship_date: YYYY-MM-DD or "tomorrow" (default, the routes being picked tonight).
        pickers_available: Night pickers on the waves. 0 = tonight's scheduled night pickers.

    Returns:
        Routes with projected departure delay, stops at risk split Retail vs Restaurant, projected OTD,
        and the at-risk customers with minutes past window.
    """
    if not dc_id:
        return error("dc_id is required.")
    plan = recommend_wave_release(dc_id, ship_date, pickers_available)
    if plan["status"] != "success":
        return plan
    crew = plan["pickers_available"]
    crew_start, crew_end = (parse_dt(x) for x in plan["crew_window"].split(" to "))
    night_hours = max(0.0, (crew_end - crew_start).total_seconds() / 3600)
    day_start = datetime.combine(crew_end.date(), SHIFT_WINDOWS["DAY"][0])
    delay_by_wave: dict[str, float] = {}
    cumulative = 0.0
    for w in plan["sequence"]:
        cumulative += w["required_picker_hours"]
        cutoff = parse_dt(w["cutoff_at"])
        if not crew:
            delay_by_wave[w["wave_id"]] = 24 * 60.0
            continue
        hours = cumulative / crew
        # Work the night crew can't finish waits for the day shift (same crew size assumed).
        finish = (crew_start + timedelta(hours=hours) if hours <= night_hours
                  else day_start + timedelta(hours=hours - night_hours))
        delay_by_wave[w["wave_id"]] = max(0.0, (finish - cutoff).total_seconds() / 60)
    d = parse_date(ship_date)
    p = {"ship_date": d}
    orders = db.query(f"""SELECT DISTINCT route_id, wave_id FROM {{outbound_orders}}
                          WHERE ship_date = :ship_date AND wave_id IS NOT NULL{dc_clause(dc_id, '', p)}""", p)
    route_delay: dict[str, float] = {}
    route_wave: dict[str, str] = {}
    for o in orders:
        dly = delay_by_wave.get(o["wave_id"], 0.0)
        if dly >= route_delay.get(o["route_id"], 0.0):
            route_delay[o["route_id"]] = dly
            route_wave[o["route_id"]] = o["wave_id"]
    sp = {"ship_date": d}
    stops = db.query(f"""
        SELECT s.route_id, s.stop_seq, s.customer_id, c.customer_name, s.segment, s.planned_arrival, s.window_end
        FROM {{route_stops}} s JOIN {{customers}} c ON c.customer_id = s.customer_id
        WHERE s.ship_date = :ship_date{dc_clause(dc_id, 's', sp)} ORDER BY s.route_id, s.stop_seq""", sp)
    at_risk, seg_tot = [], {}
    routes: dict[str, dict] = {}
    for s in stops:
        dly = route_delay.get(s["route_id"], 0.0)
        proj = parse_dt(s["planned_arrival"]) + timedelta(minutes=dly)
        past = (proj - parse_dt(s["window_end"])).total_seconds() / 60
        t = seg_tot.setdefault(s["segment"], {"stops": 0, "at_risk": 0})
        t["stops"] += 1
        rr = routes.setdefault(s["route_id"], {"route_id": s["route_id"], "wave_id": route_wave.get(s["route_id"]),
                                               "projected_departure_delay_min": round(dly), "stops": 0,
                                               "stops_at_risk": 0, "segment": s["segment"]})
        rr["stops"] += 1
        if past > 0:
            t["at_risk"] += 1
            rr["stops_at_risk"] += 1
            at_risk.append({"route_id": s["route_id"], "stop_seq": s["stop_seq"], "customer": s["customer_name"],
                            "segment": s["segment"], "window_end": s["window_end"], "minutes_past_window": round(past)})
    for t in seg_tot.values():
        t["projected_otd_pct"] = pct(t["stops"] - t["at_risk"], t["stops"])
    late_routes = sorted([r for r in routes.values() if r["projected_departure_delay_min"] > 0],
                         key=lambda r: -r["stops_at_risk"])
    at_risk.sort(key=lambda x: -x["minutes_past_window"])
    return ok(dc_id=dc_id.upper(), ship_date=d.isoformat(), pickers_on_waves=crew, by_segment=seg_tot,
              routes_departing_late=late_routes, stops_at_risk=at_risk[:15], total_stops_at_risk=len(at_risk),
              assumption="Pickers work earliest-deadline-first; work the night crew can't finish by the end of the "
                         "night shift waits for the day shift. Loading takes the 90 minutes between wave cutoff and "
                         "departure, so minutes past cutoff become minutes of late departure; drive and dwell follow "
                         "the PC*MILER plan.")
