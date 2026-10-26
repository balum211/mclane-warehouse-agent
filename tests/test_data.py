"""The generator produces consistent data with the planted scenarios the demo relies on."""

from warehouse_agent import db
from warehouse_data.schema import TABLES, ddl


def test_every_table_loaded():
    for table in TABLES:
        if table == "agent_actions":
            continue
        n = db.query(f"SELECT COUNT(*) AS n FROM {{{table}}}")[0]["n"]
        assert n > 0, table


def test_ddl_renders_for_all_backends():
    for backend in ("sqlite", "bigquery", "postgres"):
        sql = ddl(backend, "mclane_wms")
        assert sql.count("CREATE TABLE") == len(TABLES)


def test_three_wms_platforms():
    rows = db.query("SELECT DISTINCT wms_system FROM {distribution_centers}")
    assert {r["wms_system"] for r in rows} == {"MANHATTAN_ACTIVE", "BLUE_YONDER", "ARGENT"}


def test_order_lines_reconcile():
    bad = db.query("SELECT COUNT(*) AS n FROM {order_lines} WHERE qty_picked + qty_short > qty_ordered")
    assert bad[0]["n"] == 0


def test_no_completed_picks_after_demo_clock():
    rows = db.query("SELECT MAX(completed_at) AS t FROM {pick_tasks}")
    assert rows[0]["t"] <= "2026-10-27 10:30:00"
