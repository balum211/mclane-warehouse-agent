"""Run every tool against DuckDB loaded with the PostgreSQL DDL.

DuckDB is strictly typed like PostgreSQL/AlloyDB and BigQuery, so this catches non-portable SQL
(string vs DATE comparisons, unused or missing parameters, dialect functions) without a cloud
database. Skipped when duckdb is not installed.
"""

from __future__ import annotations

import re

import pytest

duckdb = pytest.importorskip("duckdb")

from warehouse_agent import db  # noqa: E402
from warehouse_agent import tools as T  # noqa: E402
from warehouse_data.schema import TABLES, ddl  # noqa: E402


class DuckBackend(db.Backend):
    name = "duckdb"
    dialect = "DuckDB (PostgreSQL-compatible test double)"

    def __init__(self, con):
        self.con = con

    def query(self, sql, params=None):
        cur = self.con.execute(db._PARAM.sub(r"$\1", self.render(sql)), params or {})
        cols = [d[0] for d in cur.description]
        return [{c: db._clean(v) for c, v in zip(cols, row)} for row in cur.fetchall()]

    def execute(self, sql, params=None):
        self.con.execute(db._PARAM.sub(r"$\1", self.render(sql)), params or {})


@pytest.fixture(scope="module")
def duck(wms_db):
    csv_dir = wms_db.parent / "csv"
    con = duckdb.connect()
    con.execute(re.sub(r"CREATE INDEX.*?;", "", ddl("postgres")))
    for t in TABLES:
        con.execute(f"COPY {t} FROM '{csv_dir}/{t}.csv' (HEADER, NULLSTR '')")
    previous = db.get_backend()
    db.set_backend(DuckBackend(con))
    yield
    db.set_backend(previous)


CALLS = [
    ("get_inventory_position", dict(sku_or_keyword="chips")), ("get_expiring_inventory", dict(dc_id="MTX")),
    ("get_replenishment_needs", dict(dc_id="MTX")), ("get_stockout_risk", dict(dc_id="MTX")),
    ("get_cycle_count_variances", dict(dc_id="MCA")), ("detect_inventory_anomalies", dict(dc_id="MTX")),
    ("analyze_slotting", dict(dc_id="MTX")), ("get_sku_affinity", dict(dc_id="MTX")),
    ("get_slot_utilization", dict(dc_id="MTX")), ("get_order_fulfillment_summary", dict(dc_id="MTX")),
    ("get_wave_progress", dict(dc_id="MTX")), ("diagnose_zone_backlog", dict(dc_id="MTX", zone="C01")),
    ("get_short_picks", dict(dc_id="MTX")), ("recommend_wave_release", dict(dc_id="MTX")),
    ("lookup_order", dict(customer_keyword="quickstop")), ("get_labor_productivity", dict(dc_id="MTX")),
    ("forecast_labor_requirement", dict(dc_id="MTX")), ("get_shift_roster", dict(dc_id="MTX")),
    ("get_dock_schedule", dict(dc_id="MTX")), ("get_dock_exceptions", dict(dc_id="MTX")),
    ("predict_dock_arrivals", dict(dc_id="MTX")), ("assess_inbound_impact", dict(dc_id="MTX")),
    ("get_door_utilization", dict(dc_id="MTX")), ("get_wms_landscape", {}), ("get_integration_health", {}),
    ("lookup_field_mapping", dict(term="sku")), ("compare_dc_kpis", {}), ("describe_data_model", {}),
    ("run_readonly_sql", dict(sql="SELECT dc_id, COUNT(*) AS n FROM inventory GROUP BY dc_id")),
    ("list_actions", {}),
    ("get_otd_performance", dict(dc_id="FDL", group_by="chain")), ("get_otd_performance", {}),
    ("get_route_status", dict(dc_id="MTX", route_id="MTX-R07")), ("assess_route_otd_risk", dict(dc_id="MTX")),
    ("get_dwell_time_changes", {}), ("get_geofence_activity", dict(dc_id="MTX")),
    ("get_route_miles", dict(dc_id="FDL", route_id="FDL-R03")), ("get_route_miles", dict(dc_id="FDL", customer_id="CFDL0023")),
    ("lookup_customer_site", dict(customer="Taco Trail")),
]


@pytest.mark.parametrize("name,kwargs", CALLS, ids=[f"{c[0]}-{i}" for i, c in enumerate(CALLS)])
def test_tool_sql_is_portable(duck, name, kwargs):
    res = getattr(T, name)(**kwargs)
    assert res["status"] == "success", res


def test_action_writes_are_portable(duck):
    a = T.propose_action("OTHER", "MTX", "portability check", "test")
    assert T.decide_action(a["action_id"], True)["action_status"] == "APPROVED"
