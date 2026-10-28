"""Regenerate sql/schema_*.sql and docs/DATA_MODEL.md from warehouse_agent/schema.py.

    python scripts/render_schema_docs.py          # row counts from data/csv (run `make data` first)
"""

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from warehouse_agent.schema import PRIMARY_KEYS, TABLES, ddl  # noqa: E402

HEADER = "-- Generated from warehouse_agent/schema.py. Do not edit by hand.\n"
GROUPS = {
    "Network and masters": ["distribution_centers", "items", "customers", "routes", "labor_standards"],
    "Facility and inventory": ["locations", "slot_assignments", "inventory", "cycle_counts"],
    "Inbound and dock": ["inbound_shipments", "asn_lines", "dock_doors", "dock_appointments"],
    "Outbound": ["outbound_orders", "order_lines", "waves", "pick_tasks"],
    "Delivery, geofences and PC*MILER": ["route_trips", "route_stops", "lane_miles", "geofences", "geofence_events"],
    "Labor": ["associates", "labor_activity", "labor_schedule"],
    "Integration and governance": ["wms_integration_events", "wms_field_map", "agent_actions"],
}
ER = """```mermaid
erDiagram
  distribution_centers ||--o{ locations : has
  distribution_centers ||--o{ dock_doors : has
  distribution_centers ||--o{ associates : employs
  distribution_centers ||--o{ customers : serves
  routes ||--o{ customers : visits
  locations ||--o| slot_assignments : pick_face
  items ||--o{ slot_assignments : slotted
  locations ||--o{ inventory : holds
  items ||--o{ inventory : stocked
  customers ||--o{ outbound_orders : places
  outbound_orders ||--|{ order_lines : contains
  waves ||--o{ pick_tasks : groups
  order_lines ||--|| pick_tasks : picked_by
  associates ||--o{ pick_tasks : performs
  inbound_shipments ||--|{ asn_lines : contains
  dock_appointments ||--o| inbound_shipments : receives
  dock_doors ||--o{ dock_appointments : hosts
  associates ||--o{ labor_activity : logs
  associates ||--o{ labor_schedule : scheduled
  locations ||--o{ cycle_counts : counted
  routes ||--o{ route_trips : runs
  route_trips ||--|{ route_stops : stops
  outbound_orders ||--|| route_stops : delivered_at
  customers ||--|| geofences : fenced_by
  geofences ||--o{ geofence_events : records
  dock_appointments ||--o{ geofence_events : yard_visit
  route_trips ||--o{ geofence_events : telematics
  customers ||--o{ lane_miles : pcmiler_lane
```"""


def counts() -> dict[str, int]:
    out = {}
    for t in TABLES:
        f = ROOT / "data" / "csv" / f"{t}.csv"
        out[t] = sum(1 for _ in csv.reader(open(f, encoding="utf-8"))) - 1 if f.exists() else 0
    return out


def main():
    (ROOT / "sql/schema_sqlite.sql").write_text(HEADER + ddl("sqlite"))
    (ROOT / "sql/schema_bigquery.sql").write_text(HEADER + ddl("bigquery", "mclane_wms"))
    (ROOT / "sql/schema_alloydb.sql").write_text(HEADER + ddl("postgres"))
    n = counts()
    assert sorted(sum(GROUPS.values(), [])) == sorted(TABLES), "add new tables to GROUPS"
    lines = ["# Data model: canonical WMS schema", "",
             "Generated from `warehouse_agent/schema.py` (the single source of truth) by",
             "`scripts/render_schema_docs.py`. One schema harmonizes Manhattan Active WM, Blue Yonder WMS and",
             "Argent; `distribution_centers.wms_system` says which platform owns each DC and `wms_field_map`",
             "maps illustrative source field names to canonical fields. The delivery tables add McLane's",
             "transportation view: PC*MILER lane miles, route trips and stops with receiving windows (on-time",
             "delivery, dwell), geofences and telematics ENTER / EXIT events. Row counts are for the default",
             "synthetic dataset (seed 27, anchor 2026-10-27 10:30).", "", ER]
    for group, tables in GROUPS.items():
        lines += ["", f"## {group}"]
        for t in tables:
            lines += ["", f"### `{t}` ({n[t]:,} rows; key: {', '.join(PRIMARY_KEYS.get(t, ()))})", "",
                      "| Column | Type | Description |", "|---|---|---|"]
            lines += [f"| `{c}` | {typ} | {d.replace('|', chr(92) + '|')} |" for c, typ, d in TABLES[t]]
    (ROOT / "docs/DATA_MODEL.md").write_text("\n".join(lines) + "\n")
    print(f"Rendered {len(TABLES)} tables")


if __name__ == "__main__":
    main()
