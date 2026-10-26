"""Tool behaviour on the synthetic data, including the planted operational problems."""

import pytest

from warehouse_agent import tools as T
from warehouse_agent.tools.analytics import validate_sql


def test_all_tools_return_status():
    calls = {
        T.get_inventory_position: dict(sku_or_keyword="chips"),
        T.get_expiring_inventory: dict(dc_id="MTX", days_ahead=5),
        T.get_replenishment_needs: dict(dc_id="MTX"),
        T.get_stockout_risk: dict(dc_id="MTX"),
        T.get_cycle_count_variances: dict(dc_id="MCA"),
        T.detect_inventory_anomalies: dict(dc_id="MTX"),
        T.analyze_slotting: dict(dc_id="MTX"),
        T.get_sku_affinity: dict(dc_id="MTX"),
        T.get_slot_utilization: dict(dc_id="MTX"),
        T.get_order_fulfillment_summary: dict(dc_id="MTX"),
        T.get_wave_progress: dict(dc_id="MTX"),
        T.diagnose_zone_backlog: dict(dc_id="MTX", zone="COOLER"),
        T.get_short_picks: dict(dc_id="MTX"),
        T.recommend_wave_release: dict(dc_id="MTX"),
        T.lookup_order: dict(customer_keyword="quickstop"),
        T.get_labor_productivity: dict(dc_id="MTX"),
        T.forecast_labor_requirement: dict(dc_id="MTX"),
        T.get_shift_roster: dict(dc_id="MTX"),
        T.get_dock_schedule: dict(dc_id="MTX"),
        T.get_dock_exceptions: dict(dc_id="MTX"),
        T.predict_dock_arrivals: dict(dc_id="MTX"),
        T.assess_inbound_impact: dict(dc_id="MTX"),
        T.get_door_utilization: dict(dc_id="MTX"),
        T.get_wms_landscape: dict(),
        T.get_integration_health: dict(),
        T.lookup_field_mapping: dict(term="sku"),
        T.compare_dc_kpis: dict(),
        T.describe_data_model: dict(),
    }
    for fn, kwargs in calls.items():
        res = fn(**kwargs)
        assert res["status"] == "success", (fn.__name__, res)


def test_missing_dc_is_an_error_not_an_exception():
    assert T.get_replenishment_needs("")["status"] == "error"


def test_planted_labor_shortfall_at_mtx():
    res = T.forecast_labor_requirement("MTX")
    assert res["verdict"] in ("SHORT", "TIGHT")
    assert res["callouts"]


def test_planted_dock_exceptions():
    res = T.get_dock_exceptions("MTX")
    assert res["summary"]["waiting_for_door"] >= 1
    assert res["summary"]["temp_mismatches"] >= 1
    assert res["summary"]["door_conflicts"] >= 1


def test_late_trailer_carries_critical_freight():
    res = T.assess_inbound_impact("MTX")
    assert res["trailers"][0]["cases_at_risk"] > 0
    assert res["trailers"][0]["status"] == "CHECKED_IN"


def test_recommend_door_respects_temperature():
    appt = T.get_dock_exceptions("MTX")["waiting_for_door"][0]
    res = T.recommend_door("MTX", appt["appointment_id"])
    assert res["status"] == "success"
    if appt["temp_zone"] in ("COOLER", "FREEZER"):
        assert all(d["temp_capable"] for d in res["candidate_doors"])


def test_anomalies_include_planted_problems():
    types = T.detect_inventory_anomalies("MTX")["anomaly_counts"]
    assert {"TEMP_ZONE_VIOLATION", "NEGATIVE_ON_HAND", "OVER_CAPACITY"} <= set(types)


def test_slotting_finds_savings():
    res = T.analyze_slotting("MTX")
    assert res["recommended_swaps"]
    for s in res["recommended_swaps"]:
        assert s["weekly_travel_saved_ft"] > 0
        assert s["from_location"].split("-")[1][0] == s["to_location"].split("-")[1][0]  # same temp zone


def test_integration_spike_on_blue_yonder():
    res = T.get_integration_health(source_system="BLUE_YONDER", hours=48)
    assert res["top_errors"][0]["error_code"] == "UOM_MISMATCH"


@pytest.mark.parametrize("sql", [
    "DELETE FROM inventory",
    "SELECT * FROM inventory; DROP TABLE items",
    "UPDATE items SET unit_cost = 0",
    "SELECT * FROM secrets",
])
def test_sql_guard_rejects(sql):
    assert validate_sql(sql) is not None
    assert T.run_readonly_sql(sql)["status"] == "error"


def test_sql_guard_allows_cte_and_joins():
    res = T.run_readonly_sql(
        "WITH s AS (SELECT sku FROM items WHERE temp_zone = 'FREEZER') "
        "SELECT COUNT(*) AS n FROM s JOIN inventory v ON v.sku = s.sku")
    assert res["status"] == "success" and res["rows"][0]["n"] > 0


def test_action_lifecycle():
    a = T.propose_action("REASSIGN_DOOR", "MTX", "Door APMTX00063 to IB03", "trailer carries critical SKUs",
                         expected_gain="protects 74 orders")
    assert a["approver_role"] == "Dock / yard lead"
    assert T.decide_action(a["action_id"], True)["action_status"] == "APPROVED"
    assert T.decide_action(a["action_id"], False)["status"] == "error"  # already decided
