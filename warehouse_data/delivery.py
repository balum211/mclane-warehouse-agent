"""Delivery-side synthetic data: geolocations, geofences, PC*MILER lane miles, route trips and
stops (Retail vs Restaurant on-time delivery, customer dwell), inbound yard history and
telematics geofence ENTER / EXIT events.

Runs after the warehouse data is built and uses its own random stream, so adding it does not
move any warehouse demo fact (labor gap, late trailer, slotting numbers).

Planted delivery problems the agents should find:
  * FDL (restaurant) trailers leaving late in the last 7 days after late waves, pulling restaurant
    OTD down versus the prior week
  * route MTX-R07 chronically late: drive times run about 28% over PC*MILER (I-35 work zone)
  * Taco Trail restaurants served by FDL: stop dwell up about 25 minutes this week
  * Lonestar Logistics at MTX: inbound yard dwell (gate in to gate out) up about 50 minutes this week
  * a trailer inside the MTX and FDL yard geofence hours before its appointment, not checked in
"""

from __future__ import annotations

import random
from datetime import date, datetime, time, timedelta

from warehouse_agent.pcmiler import destination_point, estimate_lane

DC_GEO = {
    "MTX": (31.0982, -97.3428), "MGA": (33.6220, -84.3691), "MCA": (34.0633, -117.6509),
    "MNY": (43.1587, -76.3327), "FDL": (32.9537, -96.8903), "FOH": (39.9612, -82.9988),
}
# Compass bearings customers may sit on (keeps Inland Empire stops out of the Pacific).
BEARINGS = {"MCA": (-40.0, 200.0)}
STD_DWELL = {"RETAIL": 22, "RESTAURANT": 35}
# Receiving window length. Restaurants take deliveries in a tight 60 minute window before opening;
# c-stores accept a 2 hour window.
WINDOW_MINUTES = {"RETAIL": 120, "RESTAURANT": 60}
GEOFENCE_RADIUS_M = {"DC_YARD": 450, "RETAIL": 120, "RESTAURANT": 90}
CHRONIC_ROUTE = "MTX-R07"
LATE_WAVE_DC = "FDL"
DWELL_CHAIN = ("FDL", "Taco Trail")
DWELL_CARRIER = ("MTX", "Lonestar Logistics")
CARRIER_LATENESS = {"Lonestar Logistics": 14, "Swift Haul": 6, "Prairie Freight": 9, "Coldline Reefer": 4,
                    "Atlas Dedicated": 2, "Bluebonnet Carriers": 8, "Northline Transport": 5}


def _dt(v):
    return v.strftime("%Y-%m-%d %H:%M:%S") if v else None


def _p(v):
    return datetime.fromisoformat(v) if v else None


class DeliveryBuilder:
    def __init__(self, gen):
        self.g = gen
        self.r = random.Random(gen.seed + 101)
        self.now: datetime = gen.now
        self.as_of: date = gen.as_of
        self.geo: dict[str, tuple[float, float]] = dict(DC_GEO)
        self.lanes: dict[tuple[str, str], dict] = {}
        self.cust: dict[str, dict] = {}

    # ------------------------------------------------------------------ helpers
    def lane(self, a: str, b: str, dc_id: str) -> dict:
        key = (a, b)
        if key not in self.lanes:
            (la, lo), (lb, lob) = self.geo[a], self.geo[b]
            est = estimate_lane(a, la, lo, b, lb, lob)
            self.lanes[key] = dict(origin_id=a, dest_id=b, dc_id=dc_id, source="PCMILER_SYNTH",
                                   computed_date=(self.as_of - timedelta(days=self.as_of.weekday())).isoformat(), **est)
        return self.lanes[key]

    def nn_order(self, start: str, ids: list[str], dc_id: str) -> list[str]:
        """Nearest-neighbour stop sequence by PC*MILER practical miles."""
        left, seq, cur = list(ids), [], start
        while left:
            nxt = min(left, key=lambda c: (self.lane(cur, c, dc_id)["practical_miles"], c))
            seq.append(nxt)
            left.remove(nxt)
            cur = nxt
        return seq

    def event(self, dc_id, site_type, site_id, asset, carrier, ref_type, ref_id, etype, ts, jitter=True):
        if ts > self.now:  # telematics can't report the future
            return
        lat, lon = self.geo[site_id]
        if jitter:
            lat, lon = lat + self.r.uniform(-0.0008, 0.0008), lon + self.r.uniform(-0.0008, 0.0008)
        self.g.add("geofence_events", event_id=self.g.nid("GE", 8), dc_id=dc_id, geofence_id=f"GF-{site_id}",
                   site_type=site_type, site_id=site_id, asset_id=asset, carrier=carrier, reference_type=ref_type,
                   reference_id=ref_id, event_type=etype, event_time=_dt(ts), latitude=round(lat, 6),
                   longitude=round(lon, 6))

    # --------------------------------------------------------------- geography
    def build_geo(self):
        r, g = self.r, self.g
        for row in g.rows["distribution_centers"]:
            lat, lon = DC_GEO[row["dc_id"]]
            row.update(latitude=lat, longitude=lon)
            g.add("geofences", geofence_id=f"GF-{row['dc_id']}", dc_id=row["dc_id"], site_type="DC_YARD",
                  site_id=row["dc_id"], name=f"{row['dc_name']} yard", latitude=lat, longitude=lon,
                  radius_m=GEOFENCE_RADIUS_M["DC_YARD"])
        cust_rows = {c["customer_id"]: c for c in g.rows["customers"]}
        for dc_id, custs in g.customers.items():
            b0, b1 = BEARINGS.get(dc_id, (0.0, 360.0))
            span = (b1 - b0) / len(g.routes[dc_id])
            route_idx = {rt["route_id"]: k for k, rt in enumerate(g.routes[dc_id])}
            dlat, dlon = DC_GEO[dc_id]
            for c in custs:
                k = route_idx[c["route_id"]]
                bearing = b0 + span * (k + r.uniform(0.1, 0.9))
                miles = r.uniform(8, 150) if c["segment"] == "RETAIL" else r.uniform(4, 110)
                lat, lon = destination_point(dlat, dlon, bearing, miles)
                self.geo[c["customer_id"]] = (lat, lon)
                self.cust[c["customer_id"]] = dict(c, latitude=lat, longitude=lon)
                g.add("geofences", geofence_id=f"GF-{c['customer_id']}", dc_id=dc_id, site_type="CUSTOMER",
                      site_id=c["customer_id"], name=c["customer_name"], latitude=lat, longitude=lon,
                      radius_m=GEOFENCE_RADIUS_M[c["segment"]])
            for c in custs:
                self.cust[c["customer_id"]]["standard_dwell_minutes"] = \
                    STD_DWELL[c["segment"]] + r.choice([-4, -2, 0, 0, 3, 6])
        self.cust_rows = cust_rows

    def set_windows(self, orders: dict):
        """Receiving windows are fixed per customer and set from the planned arrivals over the days the
        customer orders (routes run a different subset of stops each day)."""
        arrivals: dict[str, list[float]] = {}
        for dc_id, routes in self.g.routes.items():
            for route in routes:
                for (rid, sd), stops in orders.items():
                    if rid != route["route_id"]:
                        continue
                    t = datetime.combine(date.fromisoformat(sd), time.fromisoformat(route["departure_time"]))
                    day0, prev = t.replace(hour=0, minute=0), dc_id
                    for cid in self.nn_order(dc_id, sorted({o["customer_id"] for o in stops}), dc_id):
                        t += timedelta(minutes=self.lane(prev, cid, dc_id)["drive_minutes"])
                        arrivals.setdefault(cid, []).append((t - day0).total_seconds() / 60)
                        t += timedelta(minutes=self.cust[cid]["standard_dwell_minutes"])
                        prev = cid
        for cid, c in self.cust.items():
            mins = sorted(arrivals.get(cid) or [600.0])
            p90 = mins[min(len(mins) - 1, int(len(mins) * 0.9))]
            we = int(-(-(p90 + 10) // 15) * 15)  # window closes after 90% of planned arrivals, rounded up
            ws = we - WINDOW_MINUTES[c["segment"]]
            c.update(delivery_window_start=f"{ws // 60:02d}:{ws % 60:02d}",
                     delivery_window_end=f"{we // 60:02d}:{we % 60:02d}")
        for cid, c in self.cust.items():
            self.cust_rows[cid].update({k: c[k] for k in ("latitude", "longitude", "delivery_window_start",
                                                     "delivery_window_end", "standard_dwell_minutes")})

    # ----------------------------------------------------------------- routes
    def build_trips(self):
        r, g = self.r, self.g
        orders: dict[tuple[str, str], list[dict]] = {}
        for o in g.rows["outbound_orders"]:
            if o["status"] != "CANCELLED":
                orders.setdefault((o["route_id"], o["ship_date"]), []).append(o)
        self.set_windows(orders)
        recent = self.as_of - timedelta(days=6)
        for dc_id, routes in g.routes.items():
            for k, route in enumerate(routes):
                tractor = f"{dc_id}-TR{k + 1:03d}"
                ships = sorted({sd for (rid, sd) in orders if rid == route["route_id"]})
                for sd in ships:
                    ship = date.fromisoformat(sd)
                    stops = orders[(route["route_id"], sd)]
                    by_cust = {o["customer_id"]: o for o in stops}
                    seq = self.nn_order(dc_id, sorted(by_cust), dc_id)
                    segment = self.cust[seq[0]]["segment"]
                    planned_dep = datetime.combine(ship, time.fromisoformat(route["departure_time"]))
                    legs = [self.lane(a, b, dc_id) for a, b in zip([dc_id] + seq, seq + [dc_id])]
                    planned_miles = round(sum(x["practical_miles"] for x in legs), 1)
                    future = ship > self.as_of
                    delay, reason = 0, None
                    if not future:
                        delay = int(max(0, r.gauss(4, 7)))
                        if r.random() < 0.05:
                            delay, reason = r.randint(25, 55), r.choice(["LATE_LOAD", "DRIVER", "EQUIPMENT"])
                        if dc_id == LATE_WAVE_DC and ship >= recent and r.random() < 0.5:
                            delay, reason = r.randint(35, 80), "LATE_WAVE"
                        if delay >= 20 and reason is None:
                            reason = "LATE_LOAD"
                    actual_dep = None if future else planned_dep + timedelta(minutes=delay)
                    trip_id = f"T{dc_id}{ship:%y%m%d}{k + 1:02d}"
                    t_plan, t_act, prev = planned_dep, actual_dep, dc_id
                    excess_dwell = excess_drive = 0.0
                    completed = 0
                    for n, cid in enumerate(seq, start=1):
                        c = self.cust[cid]
                        leg = self.lane(prev, cid, dc_id)
                        std = c["standard_dwell_minutes"]
                        t_plan = t_plan + timedelta(minutes=leg["drive_minutes"])
                        ws = datetime.combine(ship, time.fromisoformat(c["delivery_window_start"]))
                        we = datetime.combine(ship, time.fromisoformat(c["delivery_window_end"]))
                        row = dict(stop_id=f"{trip_id}-{n:02d}", trip_id=trip_id, dc_id=dc_id,
                                   route_id=route["route_id"], ship_date=sd, stop_seq=n, customer_id=cid,
                                   segment=c["segment"], order_id=by_cust[cid]["order_id"],
                                   miles_from_prev=leg["practical_miles"], window_start=_dt(ws), window_end=_dt(we),
                                   planned_arrival=_dt(t_plan), eta=None, actual_arrival=None, actual_departure=None,
                                   dwell_minutes=None, standard_dwell_minutes=std, on_time=None, late_minutes=None,
                                   late_reason=None, status="PLANNED")
                        if t_act is not None:
                            factor = max(0.85, r.gauss(1.0, 0.06))
                            if route["route_id"] == CHRONIC_ROUTE:
                                factor *= 1.28
                            drive = leg["drive_minutes"] * factor
                            excess_drive += drive - leg["drive_minutes"]
                            arr = t_act + timedelta(minutes=drive)
                            dwell = max(std * 0.6, r.gauss(std, std * 0.15))
                            if (dc_id, c["chain"]) == DWELL_CHAIN and ship >= recent:
                                dwell += r.uniform(18, 32)
                            dep = arr + timedelta(minutes=dwell)
                            if arr <= self.now:
                                late = max(0, int((arr - we).total_seconds() // 60))
                                row.update(actual_arrival=_dt(arr), status="AT_STOP")
                                if dep <= self.now:
                                    row.update(actual_departure=_dt(dep), dwell_minutes=int(round(dwell)),
                                               status="DELIVERED")
                                    completed += 1
                                row.update(on_time=int(late == 0), late_minutes=late)
                                if late:
                                    if t_plan > we:
                                        why = "ROUTE_PLAN"
                                    elif delay >= 20:
                                        why = "LATE_DEPARTURE"
                                    elif excess_dwell >= excess_drive:
                                        why = "CUSTOMER_DWELL"
                                    else:
                                        why = "TRAFFIC"
                                    row["late_reason"] = why
                                self.event(dc_id, "CUSTOMER", cid, tractor, "McLane Fleet", "TRIP", trip_id, "ENTER", arr)
                                if dep <= self.now:
                                    self.event(dc_id, "CUSTOMER", cid, tractor, "McLane Fleet", "TRIP", trip_id,
                                               "EXIT", dep)
                            else:
                                row.update(eta=_dt(arr), status="EN_ROUTE")
                            excess_dwell += dwell - std
                            t_act = dep
                        t_plan = t_plan + timedelta(minutes=std)
                        prev = cid
                        g.add("route_stops", **row)
                    returned = None
                    if t_act is not None:
                        back = t_act + timedelta(minutes=legs[-1]["drive_minutes"] * max(0.9, r.gauss(1.0, 0.05)))
                        self.event(dc_id, "DC_YARD", dc_id, tractor, "McLane Fleet", "TRIP", trip_id, "EXIT", actual_dep)
                        if back <= self.now:
                            returned = back
                            self.event(dc_id, "DC_YARD", dc_id, tractor, "McLane Fleet", "TRIP", trip_id, "ENTER", back)
                    status = "PLANNED" if future else ("COMPLETED" if returned else "IN_TRANSIT")
                    g.add("route_trips", trip_id=trip_id, dc_id=dc_id, route_id=route["route_id"], ship_date=sd,
                          segment=segment, tractor_id=tractor, planned_departure=_dt(planned_dep),
                          actual_departure=_dt(actual_dep), departure_delay_minutes=None if future else delay,
                          delay_reason=reason, planned_miles=planned_miles,
                          actual_miles=round(planned_miles * r.gauss(1.02, 0.015), 1) if returned else None,
                          stops_planned=len(seq), stops_completed=completed, returned_at=_dt(returned), status=status)
        for lane in self.lanes.values():
            g.add("lane_miles", **lane)

    # ------------------------------------------------------------- inbound yard
    def build_yard(self):
        """Inbound yard visits: 11 more days of completed appointments for dwell baselines, and
        DC yard geofence events for every inbound trailer that has reached the gate."""
        r, g = self.r, self.g
        recent = self.as_of - timedelta(days=6)
        for dc_id in [d["dc_id"] for d in g.rows["distribution_centers"]]:
            ib = [d for d in g.doors[dc_id] if d["door_type"] == "INBOUND"]
            items = g.dc_items[dc_id]
            for back in range(13, 2, -1):
                day = self.as_of - timedelta(days=back)
                door_free = {d["door_id"]: datetime.combine(day, time(5, 0)) for d in ib}
                for k in range(14):
                    zone = r.choices(["DRY", "COOLER", "FREEZER"], weights=[0.55, 0.22, 0.23])[0]
                    carrier = r.choice(list(CARRIER_LATENESS))
                    start = datetime.combine(day, time(6, 0)) + timedelta(minutes=40 * k + r.choice([0, 15]))
                    end = start + timedelta(minutes=r.choice([60, 90, 120]))
                    arrival = start + timedelta(minutes=int(r.gauss(CARRIER_LATENESS[carrier], 18)))
                    wait = r.randint(10, 40)
                    if (dc_id, carrier) == DWELL_CARRIER and day >= recent:
                        wait += r.randint(35, 55)
                    cands = [d for d in ib if (d["temp_capable"] or zone == "DRY")]
                    door = min(cands, key=lambda d: door_free[d["door_id"]])
                    assigned = max(arrival + timedelta(minutes=wait), door_free[door["door_id"]])
                    done = assigned + timedelta(minutes=r.randint(45, 100))
                    door_free[door["door_id"]] = done
                    appt, asn = g.nid(f"AP{dc_id}", 5), g.nid("ASN", 7)
                    g.add("dock_appointments", appointment_id=appt, dc_id=dc_id, door_id=door["door_id"],
                          direction="INBOUND", carrier=carrier, reference_id=asn, temp_zone=zone,
                          scheduled_start=_dt(start), scheduled_end=_dt(end), actual_arrival=_dt(arrival),
                          door_assigned_at=_dt(assigned), completed_at=_dt(done), status="COMPLETED")
                    lines = r.sample([i for i in items if i["temp_zone"] == zone] or items, k=3)
                    total = 0
                    for ln, it in enumerate(lines, start=1):
                        q = r.randint(40, 200)
                        total += q
                        g.add("asn_lines", asn_id=asn, line_number=ln, dc_id=dc_id, sku=it["sku"], cases_expected=q,
                              cases_received=q)
                    g.add("inbound_shipments", asn_id=asn, dc_id=dc_id, po_number=f"PO{r.randint(4000000, 4999999)}",
                          supplier=r.choice(sorted({i["supplier"] for i in items})), appointment_id=appt,
                          expected_date=day.isoformat(), temp_zone=zone, pallets=r.randint(6, 26), cases=total,
                          status="RECEIVED")

        trailer_no: dict[str, int] = {}
        appts = [a for a in g.rows["dock_appointments"] if a["direction"] == "INBOUND"]
        for a in sorted(appts, key=lambda x: x["scheduled_start"]):
            if not a["actual_arrival"]:
                continue
            dc_id, carrier = a["dc_id"], a["carrier"]
            initials = "".join(w[0] for w in carrier.split())
            trailer_no[initials] = trailer_no.get(initials, 0) + 1
            asset = f"{initials}-{53000 + trailer_no[initials] * 7 % 9000}"
            a["_asset"] = asset
            enter = _p(a["actual_arrival"]) - timedelta(minutes=r.randint(3, 10))
            self.event(dc_id, "DC_YARD", dc_id, asset, carrier, "APPOINTMENT", a["appointment_id"], "ENTER", enter)
            if a["completed_at"]:
                lag = r.randint(8, 20)
                if (dc_id, carrier) == DWELL_CARRIER and _p(a["scheduled_start"]).date() >= recent:
                    lag += r.randint(25, 40)  # waiting on paperwork / seal at the gate
                leave = _p(a["completed_at"]) + timedelta(minutes=lag)
                if leave <= self.now:
                    self.event(dc_id, "DC_YARD", dc_id, asset, carrier, "APPOINTMENT", a["appointment_id"], "EXIT",
                               leave)

        # A trailer inside the yard geofence hours early that has not checked in at the gate.
        for dc_id, mins in (("MTX", 25), ("FDL", 40)):
            today = [a for a in appts if a["dc_id"] == dc_id and a["status"] == "SCHEDULED"
                     and a["scheduled_start"].startswith(self.as_of.isoformat())]
            if today:
                a = today[-1]
                initials = "".join(w[0] for w in a["carrier"].split())
                self.event(dc_id, "DC_YARD", dc_id, f"{initials}-58{len(today):03d}", a["carrier"], "APPOINTMENT",
                           a["appointment_id"], "ENTER", self.now - timedelta(minutes=mins))
        for a in appts:
            a.pop("_asset", None)

    def run(self):
        self.build_geo()
        self.build_trips()
        self.build_yard()
