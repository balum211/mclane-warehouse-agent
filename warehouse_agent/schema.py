"""Canonical WMS schema shared by the generator, the loaders and the agent tools.

One definition renders DDL for three backends:
  * SQLite    - local development and tests (zero setup)
  * BigQuery  - analytics / Gemini Enterprise demo backend
  * AlloyDB   - PostgreSQL-compatible operational backend

The model is a *harmonized* view across the three WMS platforms McLane runs
(Manhattan Active WM, Blue Yonder WMS, Argent). Every operational table carries
`dc_id`, and `distribution_centers.wms_system` tells you which source system
owns that building. Source-native field names live in `wms_field_map`.
"""

from __future__ import annotations

# Logical types: STRING, INT, FLOAT, DATE, DATETIME
TABLES: dict[str, list[tuple[str, str, str]]] = {
    "distribution_centers": [
        ("dc_id", "STRING", "Distribution center code, e.g. MTX"),
        ("dc_name", "STRING", "Display name"),
        ("city", "STRING", ""),
        ("state", "STRING", "US state code"),
        ("segment", "STRING", "RETAIL (convenience/grocery) or RESTAURANT (foodservice/QSR)"),
        ("wms_system", "STRING", "MANHATTAN_ACTIVE | BLUE_YONDER | ARGENT"),
        ("square_feet", "INT", ""),
        ("timezone", "STRING", "IANA timezone"),
    ],
    "items": [
        ("sku", "STRING", "Canonical item id"),
        ("description", "STRING", ""),
        ("category", "STRING", "Merchandise category"),
        ("segment", "STRING", "RETAIL | RESTAURANT | BOTH"),
        ("temp_zone", "STRING", "DRY | COOLER | FREEZER"),
        ("uom", "STRING", "Selling unit of measure (CS = case)"),
        ("case_pack", "INT", "Eaches per case"),
        ("case_cube_ft", "FLOAT", "Cubic feet per case"),
        ("case_weight_lb", "FLOAT", ""),
        ("unit_cost", "FLOAT", "Cost per case, USD"),
        ("shelf_life_days", "INT", "0 = not date controlled"),
        ("supplier", "STRING", ""),
    ],
    "customers": [
        ("customer_id", "STRING", ""),
        ("customer_name", "STRING", "Store / restaurant name"),
        ("chain", "STRING", "Banner or brand"),
        ("segment", "STRING", "RETAIL | RESTAURANT"),
        ("dc_id", "STRING", "Servicing DC"),
        ("route_id", "STRING", "Delivery route"),
        ("city", "STRING", ""),
        ("state", "STRING", ""),
    ],
    "routes": [
        ("route_id", "STRING", ""),
        ("dc_id", "STRING", ""),
        ("departure_time", "STRING", "Planned trailer departure HH:MM local"),
        ("stops", "INT", "Customers on the route"),
        ("trailer_type", "STRING", "DRY | MULTI_TEMP"),
    ],
    "locations": [
        ("location_id", "STRING", "DC-zone-aisle-bay-level"),
        ("dc_id", "STRING", ""),
        ("zone", "STRING", "DRY | COOLER | FREEZER"),
        ("aisle", "STRING", ""),
        ("bay", "INT", ""),
        ("level", "INT", "1 = floor"),
        ("location_type", "STRING", "PICK | RESERVE"),
        ("is_golden_zone", "INT", "1 = waist-height pick face near the front of the aisle"),
        ("capacity_cases", "INT", ""),
        ("distance_to_dock_ft", "FLOAT", "Travel distance from the shipping dock"),
        ("pick_sequence", "INT", "Walk sequence for pick path"),
    ],
    "slot_assignments": [
        ("dc_id", "STRING", ""),
        ("location_id", "STRING", "PICK location"),
        ("sku", "STRING", ""),
        ("min_qty", "INT", "Replenishment trigger, cases"),
        ("max_qty", "INT", "Replenish-up-to, cases"),
        ("assigned_date", "DATE", ""),
    ],
    "inventory": [
        ("inventory_id", "STRING", ""),
        ("dc_id", "STRING", ""),
        ("location_id", "STRING", ""),
        ("sku", "STRING", ""),
        ("lot_number", "STRING", ""),
        ("qty_on_hand", "INT", "Cases"),
        ("qty_allocated", "INT", "Cases allocated to open orders"),
        ("status", "STRING", "AVAILABLE | HOLD | DAMAGED | QC"),
        ("received_date", "DATE", ""),
        ("expiry_date", "DATE", "NULL when not date controlled"),
    ],
    "inbound_shipments": [
        ("asn_id", "STRING", "Advance ship notice"),
        ("dc_id", "STRING", ""),
        ("po_number", "STRING", ""),
        ("supplier", "STRING", ""),
        ("appointment_id", "STRING", ""),
        ("expected_date", "DATE", ""),
        ("temp_zone", "STRING", ""),
        ("pallets", "INT", ""),
        ("cases", "INT", ""),
        ("status", "STRING", "SCHEDULED | ARRIVED | RECEIVING | RECEIVED | CANCELLED"),
    ],
    "asn_lines": [
        ("asn_id", "STRING", ""),
        ("line_number", "INT", ""),
        ("dc_id", "STRING", ""),
        ("sku", "STRING", ""),
        ("cases_expected", "INT", ""),
        ("cases_received", "INT", ""),
    ],
    "outbound_orders": [
        ("order_id", "STRING", ""),
        ("dc_id", "STRING", ""),
        ("customer_id", "STRING", ""),
        ("route_id", "STRING", ""),
        ("order_date", "DATE", ""),
        ("ship_date", "DATE", ""),
        ("wave_id", "STRING", "NULL until waved"),
        ("status", "STRING", "NEW | RELEASED | PICKING | PICKED | LOADED | SHIPPED | CANCELLED"),
        ("priority", "INT", "1 = highest"),
        ("total_lines", "INT", ""),
        ("total_cases", "INT", ""),
    ],
    "order_lines": [
        ("order_id", "STRING", ""),
        ("line_number", "INT", ""),
        ("dc_id", "STRING", ""),
        ("sku", "STRING", ""),
        ("qty_ordered", "INT", "Cases"),
        ("qty_picked", "INT", "Cases"),
        ("qty_short", "INT", "Cases"),
        ("short_reason", "STRING", "NULL | NO_STOCK | STOCK_ON_HOLD | PICK_FACE_EMPTY | DAMAGED"),
    ],
    "waves": [
        ("wave_id", "STRING", ""),
        ("dc_id", "STRING", ""),
        ("ship_date", "DATE", ""),
        ("wave_type", "STRING", "ROUTE | TEMP_ZONE | RUSH"),
        ("temp_zone", "STRING", ""),
        ("released_at", "DATETIME", ""),
        ("cutoff_at", "DATETIME", "Pick must finish by (trailer departure - load time)"),
        ("status", "STRING", "PLANNED | RELEASED | IN_PROGRESS | COMPLETE"),
        ("order_count", "INT", ""),
        ("line_count", "INT", ""),
    ],
    "pick_tasks": [
        ("task_id", "STRING", ""),
        ("dc_id", "STRING", ""),
        ("wave_id", "STRING", ""),
        ("order_id", "STRING", ""),
        ("line_number", "INT", ""),
        ("sku", "STRING", ""),
        ("location_id", "STRING", ""),
        ("qty", "INT", "Cases to pick"),
        ("qty_picked", "INT", ""),
        ("associate_id", "STRING", ""),
        ("status", "STRING", "OPEN | ASSIGNED | IN_PROGRESS | COMPLETE | SHORT"),
        ("created_at", "DATETIME", ""),
        ("completed_at", "DATETIME", ""),
        ("travel_ft", "FLOAT", "Round-trip travel for this task"),
    ],
    "associates": [
        ("associate_id", "STRING", ""),
        ("dc_id", "STRING", ""),
        ("associate_name", "STRING", ""),
        ("role", "STRING", "PICKER | LOADER | RECEIVER | FORKLIFT"),
        ("home_zone", "STRING", "DRY | COOLER | FREEZER"),
        ("shift", "STRING", "DAY | NIGHT"),
        ("hire_date", "DATE", ""),
        ("hourly_rate", "FLOAT", "USD"),
    ],
    "labor_standards": [
        ("role", "STRING", ""),
        ("zone", "STRING", ""),
        ("engineered_rate", "FLOAT", "Cases per hour at 100% performance"),
    ],
    "labor_activity": [
        ("activity_id", "STRING", ""),
        ("dc_id", "STRING", ""),
        ("associate_id", "STRING", ""),
        ("work_date", "DATE", ""),
        ("role", "STRING", ""),
        ("zone", "STRING", ""),
        ("cases_handled", "INT", ""),
        ("direct_hours", "FLOAT", ""),
        ("indirect_hours", "FLOAT", "Meetings, travel to zone, equipment issues"),
    ],
    "labor_schedule": [
        ("dc_id", "STRING", ""),
        ("associate_id", "STRING", ""),
        ("work_date", "DATE", ""),
        ("shift", "STRING", ""),
        ("scheduled_hours", "FLOAT", ""),
        ("status", "STRING", "SCHEDULED | PTO | CALLOUT"),
    ],
    "dock_doors": [
        ("door_id", "STRING", ""),
        ("dc_id", "STRING", ""),
        ("door_type", "STRING", "INBOUND | OUTBOUND"),
        ("temp_capable", "INT", "1 = refrigerated seal / reefer plug"),
    ],
    "dock_appointments": [
        ("appointment_id", "STRING", ""),
        ("dc_id", "STRING", ""),
        ("door_id", "STRING", ""),
        ("direction", "STRING", "INBOUND | OUTBOUND"),
        ("carrier", "STRING", ""),
        ("reference_id", "STRING", "ASN id (inbound) or route id (outbound)"),
        ("temp_zone", "STRING", "Most restrictive temp zone on the trailer"),
        ("scheduled_start", "DATETIME", ""),
        ("scheduled_end", "DATETIME", ""),
        ("actual_arrival", "DATETIME", "NULL = not arrived"),
        ("door_assigned_at", "DATETIME", ""),
        ("completed_at", "DATETIME", ""),
        ("status", "STRING", "SCHEDULED | CHECKED_IN | AT_DOOR | COMPLETED | NO_SHOW"),
    ],
    "cycle_counts": [
        ("count_id", "STRING", ""),
        ("dc_id", "STRING", ""),
        ("location_id", "STRING", ""),
        ("sku", "STRING", ""),
        ("count_date", "DATE", ""),
        ("system_qty", "INT", ""),
        ("counted_qty", "INT", ""),
        ("variance_qty", "INT", "counted - system"),
        ("variance_value", "FLOAT", "USD"),
        ("counter_id", "STRING", ""),
    ],
    "wms_integration_events": [
        ("event_id", "STRING", ""),
        ("dc_id", "STRING", ""),
        ("source_system", "STRING", "MANHATTAN_ACTIVE | BLUE_YONDER | ARGENT"),
        ("interface", "STRING", "Canonical interface, e.g. ITEM_MASTER, ASN, ORDER_RELEASE, SHIP_CONFIRM"),
        ("source_message_type", "STRING", "Source-native message name (illustrative)"),
        ("event_time", "DATETIME", ""),
        ("status", "STRING", "SUCCESS | ERROR | RETRY"),
        ("error_code", "STRING", ""),
        ("error_detail", "STRING", ""),
        ("reference_id", "STRING", "Order, ASN or SKU the message is about"),
    ],
    "wms_field_map": [
        ("source_system", "STRING", ""),
        ("source_entity", "STRING", ""),
        ("source_field", "STRING", "Illustrative source-native name"),
        ("canonical_table", "STRING", ""),
        ("canonical_field", "STRING", ""),
        ("transform_rule", "STRING", ""),
    ],
    "agent_actions": [
        ("action_id", "STRING", ""),
        ("created_at", "DATETIME", ""),
        ("dc_id", "STRING", ""),
        ("action_type", "STRING", "REPLENISH | RESLOT | REASSIGN_DOOR | RELEASE_WAVE | REBALANCE_LABOR | CYCLE_COUNT | OTHER"),
        ("details", "STRING", "JSON payload"),
        ("rationale", "STRING", ""),
        ("status", "STRING", "PROPOSED | APPROVED | REJECTED"),
        ("decided_at", "DATETIME", ""),
    ],
}

_SQLITE = {"STRING": "TEXT", "INT": "INTEGER", "FLOAT": "REAL", "DATE": "TEXT", "DATETIME": "TEXT"}
_BIGQUERY = {"STRING": "STRING", "INT": "INT64", "FLOAT": "FLOAT64", "DATE": "DATE", "DATETIME": "DATETIME"}
_POSTGRES = {"STRING": "TEXT", "INT": "BIGINT", "FLOAT": "DOUBLE PRECISION", "DATE": "DATE", "DATETIME": "TIMESTAMP"}

# Primary keys / indexes for the relational backends (BigQuery uses clustering instead).
PRIMARY_KEYS: dict[str, tuple[str, ...]] = {
    "distribution_centers": ("dc_id",),
    "items": ("sku",),
    "customers": ("customer_id",),
    "routes": ("route_id",),
    "locations": ("location_id",),
    "slot_assignments": ("location_id",),
    "inventory": ("inventory_id",),
    "inbound_shipments": ("asn_id",),
    "asn_lines": ("asn_id", "line_number"),
    "outbound_orders": ("order_id",),
    "order_lines": ("order_id", "line_number"),
    "waves": ("wave_id",),
    "pick_tasks": ("task_id",),
    "associates": ("associate_id",),
    "labor_standards": ("role", "zone"),
    "labor_activity": ("activity_id",),
    "labor_schedule": ("associate_id", "work_date"),
    "dock_doors": ("door_id",),
    "dock_appointments": ("appointment_id",),
    "cycle_counts": ("count_id",),
    "wms_integration_events": ("event_id",),
    "agent_actions": ("action_id",),
}


def columns(table: str) -> list[str]:
    return [c[0] for c in TABLES[table]]


def ddl(backend: str, dataset: str | None = None) -> str:
    """Render CREATE TABLE statements for `sqlite`, `bigquery` or `postgres`."""
    types = {"sqlite": _SQLITE, "bigquery": _BIGQUERY, "postgres": _POSTGRES}[backend]
    out = []
    for table, cols in TABLES.items():
        name = f"`{dataset}.{table}`" if backend == "bigquery" and dataset else table
        lines = []
        for col, typ, desc in cols:
            line = f"  {col} {types[typ]}"
            if backend == "bigquery" and desc:
                line += f" OPTIONS(description={_bq_str(desc)})"
            lines.append(line)
        pk = PRIMARY_KEYS.get(table)
        if pk and backend in ("sqlite", "postgres"):
            lines.append(f"  PRIMARY KEY ({', '.join(pk)})")
        body = ",\n".join(lines)
        suffix = ""
        if backend == "bigquery" and "dc_id" in columns(table) and table != "distribution_centers":
            suffix = "\nCLUSTER BY dc_id"
        out.append(f"CREATE TABLE IF NOT EXISTS {name} (\n{body}\n){suffix};")
    if backend in ("sqlite", "postgres"):
        for table in TABLES:
            if "dc_id" in columns(table) and table != "distribution_centers":
                out.append(f"CREATE INDEX IF NOT EXISTS ix_{table}_dc ON {table} (dc_id);")
        out.append("CREATE INDEX IF NOT EXISTS ix_inventory_sku ON inventory (sku);")
        out.append("CREATE INDEX IF NOT EXISTS ix_order_lines_sku ON order_lines (sku);")
        out.append("CREATE INDEX IF NOT EXISTS ix_orders_ship ON outbound_orders (dc_id, ship_date);")
        out.append("CREATE INDEX IF NOT EXISTS ix_pick_tasks_wave ON pick_tasks (wave_id);")
    return "\n\n".join(out) + "\n"


def _bq_str(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


if __name__ == "__main__":
    import sys

    print(ddl(sys.argv[1] if len(sys.argv) > 1 else "sqlite"))
