"""Delivery-side data and tools: geofences, PC*MILER miles, dwell changes, Retail vs Restaurant OTD."""

from warehouse_agent import db, pcmiler
from warehouse_agent import tools as T


def test_every_customer_and_dc_is_geolocated_with_a_geofence():
    missing = db.query("SELECT COUNT(*) AS n FROM {customers} WHERE latitude IS NULL OR delivery_window_end IS NULL")
    assert missing[0]["n"] == 0
    n = db.query("SELECT COUNT(*) AS n FROM {geofences}")[0]["n"]
    sites = db.query("SELECT COUNT(*) AS n FROM {customers}")[0]["n"] + 6
    assert n == sites


def test_restaurant_windows_are_60_minutes_and_retail_120():
    for seg, minutes in (("RESTAURANT", 60), ("RETAIL", 120)):
        row = db.query("SELECT delivery_window_start AS s, delivery_window_end AS e FROM {customers} "
                       "WHERE segment = :seg LIMIT 1", {"seg": seg})[0]
        h1, m1 = map(int, row["s"].split(":"))
        h2, m2 = map(int, row["e"].split(":"))
        assert (h2 * 60 + m2) - (h1 * 60 + m1) == minutes


def test_stops_match_orders_and_trips():
    n_orders = db.query("SELECT COUNT(*) AS n FROM {outbound_orders} WHERE status <> 'CANCELLED'")[0]["n"]
    n_stops = db.query("SELECT COUNT(*) AS n FROM {route_stops}")[0]["n"]
    assert n_orders == n_stops
    future = db.query("SELECT COUNT(*) AS n FROM {route_stops} WHERE ship_date > '2026-10-27' AND on_time IS NOT NULL")
    assert future[0]["n"] == 0
    after_clock = db.query("SELECT MAX(event_time) AS t FROM {geofence_events}")[0]["t"]
    assert after_clock <= "2026-10-27 10:30:00"


def test_pcmiler_fallbacks():
    est = pcmiler.estimate_lane("MTX", 31.0982, -97.3428, "FDL", 32.9537, -96.8903)
    assert 140 < est["practical_miles"] < 175  # Temple TX -> Carrollton TX is about 155 road miles
    lane = T.get_route_miles("MTX", customer_id="CMTX0001")["lane"]
    assert lane["source"] == "PCMILER_SYNTH" and lane["practical_miles"] > 0
    route = T.get_route_miles("FDL", route_id="FDL-R03")
    assert route["total_practical_miles"] > 0 and route["legs"][0]["from"] == "FDL"


def test_restaurant_otd_dropped_at_fdl_from_late_departures():
    res = T.get_otd_performance("FDL")
    assert res["overall_current"]["otd_pct"] < res["overall_prior_otd_pct"] - 10
    assert next(iter(res["overall_current"]["late_reasons"])) == "LATE_DEPARTURE"
    allr = T.get_otd_performance()
    assert allr["by_segment"]["RESTAURANT"]["otd_pct"] < allr["by_segment"]["RETAIL"]["otd_pct"]


def test_chronic_late_route_is_worst_at_mtx():
    res = T.get_otd_performance("MTX", group_by="route")
    assert res["groups"][0]["route"] == "MTX-R07"
    assert "TRAFFIC" in res["groups"][0]["current"]["late_reasons"]


def test_dwell_increases_are_found():
    res = T.get_dwell_time_changes()
    top_in = res["inbound_yard"][0]
    assert (top_in["dc_id"], top_in["carrier"]) == ("MTX", "Lonestar Logistics") and top_in["change_min"] > 30
    top_cust = res["customer_stops"][0]
    assert (top_cust["dc_id"], top_cust["chain"]) == ("FDL", "Taco Trail") and top_cust["change_min"] > 15


def test_geofence_flags_trailer_in_yard_not_checked_in():
    res = T.get_geofence_activity("MTX")
    flags = {f["flag"] for f in res["exceptions"]}
    assert {"IN_YARD_NOT_CHECKED_IN", "DETENTION_RISK"} <= flags
    assert res["trucks_at_customers"]


def test_wave_risk_becomes_missed_windows_and_replan_clears_it():
    before = T.assess_route_otd_risk("MTX")
    assert before["pickers_on_waves"] == 2 and before["total_stops_at_risk"] > 0
    after = T.assess_route_otd_risk("MTX", pickers_available=5)
    assert after["total_stops_at_risk"] == 0


def test_live_route_status_has_projected_late_stops():
    res = T.get_route_status("MTX")
    assert res["by_segment"]["RETAIL"]["late_or_projected_late"] > 0
    assert any(r["trip_status"] == "IN_TRANSIT" for r in res["routes"])
