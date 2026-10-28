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
        ("latitude", "FLOAT", "DC yard gate latitude (WGS84)"),
        ("longitude", "FLOAT", "DC yard gate longitude (WGS84)"),
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
        ("latitude", "FLOAT", "Delivery point latitude (WGS84)"),
        ("longitude", "FLOAT", "Delivery point longitude (WGS84)"),
        ("delivery_window_start", "STRING", "Receiving window start HH:MM local (restaurant 60 min, retail 120 min)"),
        ("delivery_window_end", "STRING", "Receiving window end HH:MM local"),
        ("standard_dwell_minutes", "INT", "Planned on-site time (unload, check-in, put-away for restaurants)"),
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
    "geofences": [
        ("geofence_id", "STRING", "GF-<site id>"),
        ("dc_id", "STRING", "Owning / servicing DC"),
        ("site_type", "STRING", "DC_YARD | CUSTOMER"),
        ("site_id", "STRING", "dc_id or customer_id"),
        ("name", "STRING", ""),
        ("latitude", "FLOAT", "Circle center"),
        ("longitude", "FLOAT", "Circle center"),
        ("radius_m", "INT", "Circle radius in meters"),
    ],
    "geofence_events": [
        ("event_id", "STRING", "Telematics event id"),
        ("dc_id", "STRING", ""),
        ("geofence_id", "STRING", ""),
        ("site_type", "STRING", "DC_YARD | CUSTOMER"),
        ("site_id", "STRING", "dc_id or customer_id"),
        ("asset_id", "STRING", "Trailer / tractor id from the telematics unit"),
        ("carrier", "STRING", ""),
        ("reference_type", "STRING", "APPOINTMENT (inbound trailer) | TRIP (McLane route)"),
        ("reference_id", "STRING", "appointment_id or trip_id"),
        ("event_type", "STRING", "ENTER | EXIT"),
        ("event_time", "DATETIME", "Local time"),
        ("latitude", "FLOAT", "Ping position"),
        ("longitude", "FLOAT", "Ping position"),
    ],
    "lane_miles": [
        ("origin_id", "STRING", "dc_id or customer_id"),
        ("dest_id", "STRING", "dc_id or customer_id"),
        ("dc_id", "STRING", ""),
        ("practical_miles", "FLOAT", "PC*MILER practical route miles (truck)"),
        ("shortest_miles", "FLOAT", "PC*MILER shortest route miles"),
        ("drive_minutes", "INT", "PC*MILER drive time"),
        ("source", "STRING", "PCMILER_SYNTH (demo) | PCMILER_API | PCMILER_BATCH"),
        ("computed_date", "DATE", ""),
    ],
    "route_trips": [
        ("trip_id", "STRING", "One trailer run of a route on a ship date"),
        ("dc_id", "STRING", ""),
        ("route_id", "STRING", ""),
        ("ship_date", "DATE", ""),
        ("segment", "STRING", "RETAIL | RESTAURANT"),
        ("tractor_id", "STRING", ""),
        ("planned_departure", "DATETIME", ""),
        ("actual_departure", "DATETIME", "DC yard geofence EXIT; NULL = not departed"),
        ("departure_delay_minutes", "INT", ""),
        ("delay_reason", "STRING", "NULL | LATE_WAVE | LATE_LOAD | DRIVER | EQUIPMENT"),
        ("planned_miles", "FLOAT", "PC*MILER practical miles, DC -> stops -> DC"),
        ("actual_miles", "FLOAT", "Odometer / telematics miles"),
        ("stops_planned", "INT", ""),
        ("stops_completed", "INT", ""),
        ("returned_at", "DATETIME", "DC yard geofence ENTER on return"),
        ("status", "STRING", "PLANNED | IN_TRANSIT | COMPLETED"),
    ],
    "route_stops": [
        ("stop_id", "STRING", ""),
        ("trip_id", "STRING", ""),
        ("dc_id", "STRING", ""),
        ("route_id", "STRING", ""),
        ("ship_date", "DATE", ""),
        ("stop_seq", "INT", ""),
        ("customer_id", "STRING", ""),
        ("segment", "STRING", "RETAIL | RESTAURANT"),
        ("order_id", "STRING", ""),
        ("miles_from_prev", "FLOAT", "PC*MILER practical miles from the previous stop (or DC)"),
        ("window_start", "DATETIME", "Customer receiving window"),
        ("window_end", "DATETIME", ""),
        ("planned_arrival", "DATETIME", ""),
        ("eta", "DATETIME", "Telematics ETA for stops not reached yet"),
        ("actual_arrival", "DATETIME", "Customer geofence ENTER"),
        ("actual_departure", "DATETIME", "Customer geofence EXIT"),
        ("dwell_minutes", "INT", "actual_departure - actual_arrival"),
        ("standard_dwell_minutes", "INT", ""),
        ("on_time", "INT", "1 = arrived by window_end (OTD); NULL until delivered"),
        ("late_minutes", "INT", ""),
        ("late_reason", "STRING", "NULL | LATE_DEPARTURE | CUSTOMER_DWELL | TRAFFIC | ROUTE_PLAN"),
        ("status", "STRING", "PLANNED | EN_ROUTE | AT_STOP | DELIVERED"),
    ],
    "agent_actions": [
        ("action_id", "STRING", ""),
        ("created_at", "DATETIME", ""),
        ("dc_id", "STRING", ""),
        ("action_type", "STRING", "REPLENISH | RESLOT | REASSIGN_DOOR | RELEASE_WAVE | REBALANCE_LABOR | CYCLE_COUNT | RESEQUENCE_ROUTE | NOTIFY_CUSTOMER | OTHER"),
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
    "geofences": ("geofence_id",),
    "geofence_events": ("event_id",),
    "lane_miles": ("origin_id", "dest_id"),
    "route_trips": ("trip_id",),
    "route_stops": ("stop_id",),
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
        out.append("CREATE INDEX IF NOT EXISTS ix_route_stops_ship ON route_stops (dc_id, ship_date);")
        out.append("CREATE INDEX IF NOT EXISTS ix_geofence_events_time ON geofence_events (dc_id, event_time);")
    return "\n\n".join(out) + "\n"


def _bq_str(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


if __name__ == "__main__":
    import sys

    print(ddl(sys.argv[1] if len(sys.argv) > 1 else "sqlite"))
