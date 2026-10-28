-- Generated from warehouse_agent/schema.py. Do not edit by hand.
CREATE TABLE IF NOT EXISTS distribution_centers (
  dc_id TEXT,
  dc_name TEXT,
  city TEXT,
  state TEXT,
  segment TEXT,
  wms_system TEXT,
  square_feet INTEGER,
  timezone TEXT,
  latitude REAL,
  longitude REAL,
  PRIMARY KEY (dc_id)
);

CREATE TABLE IF NOT EXISTS items (
  sku TEXT,
  description TEXT,
  category TEXT,
  segment TEXT,
  temp_zone TEXT,
  uom TEXT,
  case_pack INTEGER,
  case_cube_ft REAL,
  case_weight_lb REAL,
  unit_cost REAL,
  shelf_life_days INTEGER,
  supplier TEXT,
  PRIMARY KEY (sku)
);

CREATE TABLE IF NOT EXISTS customers (
  customer_id TEXT,
  customer_name TEXT,
  chain TEXT,
  segment TEXT,
  dc_id TEXT,
  route_id TEXT,
  city TEXT,
  state TEXT,
  latitude REAL,
  longitude REAL,
  delivery_window_start TEXT,
  delivery_window_end TEXT,
  standard_dwell_minutes INTEGER,
  PRIMARY KEY (customer_id)
);

CREATE TABLE IF NOT EXISTS routes (
  route_id TEXT,
  dc_id TEXT,
  departure_time TEXT,
  stops INTEGER,
  trailer_type TEXT,
  PRIMARY KEY (route_id)
);

CREATE TABLE IF NOT EXISTS locations (
  location_id TEXT,
  dc_id TEXT,
  zone TEXT,
  aisle TEXT,
  bay INTEGER,
  level INTEGER,
  location_type TEXT,
  is_golden_zone INTEGER,
  capacity_cases INTEGER,
  distance_to_dock_ft REAL,
  pick_sequence INTEGER,
  PRIMARY KEY (location_id)
);

CREATE TABLE IF NOT EXISTS slot_assignments (
  dc_id TEXT,
  location_id TEXT,
  sku TEXT,
  min_qty INTEGER,
  max_qty INTEGER,
  assigned_date TEXT,
  PRIMARY KEY (location_id)
);

CREATE TABLE IF NOT EXISTS inventory (
  inventory_id TEXT,
  dc_id TEXT,
  location_id TEXT,
  sku TEXT,
  lot_number TEXT,
  qty_on_hand INTEGER,
  qty_allocated INTEGER,
  status TEXT,
  received_date TEXT,
  expiry_date TEXT,
  PRIMARY KEY (inventory_id)
);

CREATE TABLE IF NOT EXISTS inbound_shipments (
  asn_id TEXT,
  dc_id TEXT,
  po_number TEXT,
  supplier TEXT,
  appointment_id TEXT,
  expected_date TEXT,
  temp_zone TEXT,
  pallets INTEGER,
  cases INTEGER,
  status TEXT,
  PRIMARY KEY (asn_id)
);

CREATE TABLE IF NOT EXISTS asn_lines (
  asn_id TEXT,
  line_number INTEGER,
  dc_id TEXT,
  sku TEXT,
  cases_expected INTEGER,
  cases_received INTEGER,
  PRIMARY KEY (asn_id, line_number)
);

CREATE TABLE IF NOT EXISTS outbound_orders (
  order_id TEXT,
  dc_id TEXT,
  customer_id TEXT,
  route_id TEXT,
  order_date TEXT,
  ship_date TEXT,
  wave_id TEXT,
  status TEXT,
  priority INTEGER,
  total_lines INTEGER,
  total_cases INTEGER,
  PRIMARY KEY (order_id)
);

CREATE TABLE IF NOT EXISTS order_lines (
  order_id TEXT,
  line_number INTEGER,
  dc_id TEXT,
  sku TEXT,
  qty_ordered INTEGER,
  qty_picked INTEGER,
  qty_short INTEGER,
  short_reason TEXT,
  PRIMARY KEY (order_id, line_number)
);

CREATE TABLE IF NOT EXISTS waves (
  wave_id TEXT,
  dc_id TEXT,
  ship_date TEXT,
  wave_type TEXT,
  temp_zone TEXT,
  released_at TEXT,
  cutoff_at TEXT,
  status TEXT,
  order_count INTEGER,
  line_count INTEGER,
  PRIMARY KEY (wave_id)
);

CREATE TABLE IF NOT EXISTS pick_tasks (
  task_id TEXT,
  dc_id TEXT,
  wave_id TEXT,
  order_id TEXT,
  line_number INTEGER,
  sku TEXT,
  location_id TEXT,
  qty INTEGER,
  qty_picked INTEGER,
  associate_id TEXT,
  status TEXT,
  created_at TEXT,
  completed_at TEXT,
  travel_ft REAL,
  PRIMARY KEY (task_id)
);

CREATE TABLE IF NOT EXISTS associates (
  associate_id TEXT,
  dc_id TEXT,
  associate_name TEXT,
  role TEXT,
  home_zone TEXT,
  shift TEXT,
  hire_date TEXT,
  hourly_rate REAL,
  PRIMARY KEY (associate_id)
);

CREATE TABLE IF NOT EXISTS labor_standards (
  role TEXT,
  zone TEXT,
  engineered_rate REAL,
  PRIMARY KEY (role, zone)
);

CREATE TABLE IF NOT EXISTS labor_activity (
  activity_id TEXT,
  dc_id TEXT,
  associate_id TEXT,
  work_date TEXT,
  role TEXT,
  zone TEXT,
  cases_handled INTEGER,
  direct_hours REAL,
  indirect_hours REAL,
  PRIMARY KEY (activity_id)
);

CREATE TABLE IF NOT EXISTS labor_schedule (
  dc_id TEXT,
  associate_id TEXT,
  work_date TEXT,
  shift TEXT,
  scheduled_hours REAL,
  status TEXT,
  PRIMARY KEY (associate_id, work_date)
);

CREATE TABLE IF NOT EXISTS dock_doors (
  door_id TEXT,
  dc_id TEXT,
  door_type TEXT,
  temp_capable INTEGER,
  PRIMARY KEY (door_id)
);

CREATE TABLE IF NOT EXISTS dock_appointments (
  appointment_id TEXT,
  dc_id TEXT,
  door_id TEXT,
  direction TEXT,
  carrier TEXT,
  reference_id TEXT,
  temp_zone TEXT,
  scheduled_start TEXT,
  scheduled_end TEXT,
  actual_arrival TEXT,
  door_assigned_at TEXT,
  completed_at TEXT,
  status TEXT,
  PRIMARY KEY (appointment_id)
);

CREATE TABLE IF NOT EXISTS cycle_counts (
  count_id TEXT,
  dc_id TEXT,
  location_id TEXT,
  sku TEXT,
  count_date TEXT,
  system_qty INTEGER,
  counted_qty INTEGER,
  variance_qty INTEGER,
  variance_value REAL,
  counter_id TEXT,
  PRIMARY KEY (count_id)
);

CREATE TABLE IF NOT EXISTS wms_integration_events (
  event_id TEXT,
  dc_id TEXT,
  source_system TEXT,
  interface TEXT,
  source_message_type TEXT,
  event_time TEXT,
  status TEXT,
  error_code TEXT,
  error_detail TEXT,
  reference_id TEXT,
  PRIMARY KEY (event_id)
);

CREATE TABLE IF NOT EXISTS wms_field_map (
  source_system TEXT,
  source_entity TEXT,
  source_field TEXT,
  canonical_table TEXT,
  canonical_field TEXT,
  transform_rule TEXT
);

CREATE TABLE IF NOT EXISTS geofences (
  geofence_id TEXT,
  dc_id TEXT,
  site_type TEXT,
  site_id TEXT,
  name TEXT,
  latitude REAL,
  longitude REAL,
  radius_m INTEGER,
  PRIMARY KEY (geofence_id)
);

CREATE TABLE IF NOT EXISTS geofence_events (
  event_id TEXT,
  dc_id TEXT,
  geofence_id TEXT,
  site_type TEXT,
  site_id TEXT,
  asset_id TEXT,
  carrier TEXT,
  reference_type TEXT,
  reference_id TEXT,
  event_type TEXT,
  event_time TEXT,
  latitude REAL,
  longitude REAL,
  PRIMARY KEY (event_id)
);

CREATE TABLE IF NOT EXISTS lane_miles (
  origin_id TEXT,
  dest_id TEXT,
  dc_id TEXT,
  practical_miles REAL,
  shortest_miles REAL,
  drive_minutes INTEGER,
  source TEXT,
  computed_date TEXT,
  PRIMARY KEY (origin_id, dest_id)
);

CREATE TABLE IF NOT EXISTS route_trips (
  trip_id TEXT,
  dc_id TEXT,
  route_id TEXT,
  ship_date TEXT,
  segment TEXT,
  tractor_id TEXT,
  planned_departure TEXT,
  actual_departure TEXT,
  departure_delay_minutes INTEGER,
  delay_reason TEXT,
  planned_miles REAL,
  actual_miles REAL,
  stops_planned INTEGER,
  stops_completed INTEGER,
  returned_at TEXT,
  status TEXT,
  PRIMARY KEY (trip_id)
);

CREATE TABLE IF NOT EXISTS route_stops (
  stop_id TEXT,
  trip_id TEXT,
  dc_id TEXT,
  route_id TEXT,
  ship_date TEXT,
  stop_seq INTEGER,
  customer_id TEXT,
  segment TEXT,
  order_id TEXT,
  miles_from_prev REAL,
  window_start TEXT,
  window_end TEXT,
  planned_arrival TEXT,
  eta TEXT,
  actual_arrival TEXT,
  actual_departure TEXT,
  dwell_minutes INTEGER,
  standard_dwell_minutes INTEGER,
  on_time INTEGER,
  late_minutes INTEGER,
  late_reason TEXT,
  status TEXT,
  PRIMARY KEY (stop_id)
);

CREATE TABLE IF NOT EXISTS agent_actions (
  action_id TEXT,
  created_at TEXT,
  dc_id TEXT,
  action_type TEXT,
  details TEXT,
  rationale TEXT,
  status TEXT,
  decided_at TEXT,
  PRIMARY KEY (action_id)
);

CREATE INDEX IF NOT EXISTS ix_customers_dc ON customers (dc_id);

CREATE INDEX IF NOT EXISTS ix_routes_dc ON routes (dc_id);

CREATE INDEX IF NOT EXISTS ix_locations_dc ON locations (dc_id);

CREATE INDEX IF NOT EXISTS ix_slot_assignments_dc ON slot_assignments (dc_id);

CREATE INDEX IF NOT EXISTS ix_inventory_dc ON inventory (dc_id);

CREATE INDEX IF NOT EXISTS ix_inbound_shipments_dc ON inbound_shipments (dc_id);

CREATE INDEX IF NOT EXISTS ix_asn_lines_dc ON asn_lines (dc_id);

CREATE INDEX IF NOT EXISTS ix_outbound_orders_dc ON outbound_orders (dc_id);

CREATE INDEX IF NOT EXISTS ix_order_lines_dc ON order_lines (dc_id);

CREATE INDEX IF NOT EXISTS ix_waves_dc ON waves (dc_id);

CREATE INDEX IF NOT EXISTS ix_pick_tasks_dc ON pick_tasks (dc_id);

CREATE INDEX IF NOT EXISTS ix_associates_dc ON associates (dc_id);

CREATE INDEX IF NOT EXISTS ix_labor_activity_dc ON labor_activity (dc_id);

CREATE INDEX IF NOT EXISTS ix_labor_schedule_dc ON labor_schedule (dc_id);

CREATE INDEX IF NOT EXISTS ix_dock_doors_dc ON dock_doors (dc_id);

CREATE INDEX IF NOT EXISTS ix_dock_appointments_dc ON dock_appointments (dc_id);

CREATE INDEX IF NOT EXISTS ix_cycle_counts_dc ON cycle_counts (dc_id);

CREATE INDEX IF NOT EXISTS ix_wms_integration_events_dc ON wms_integration_events (dc_id);

CREATE INDEX IF NOT EXISTS ix_geofences_dc ON geofences (dc_id);

CREATE INDEX IF NOT EXISTS ix_geofence_events_dc ON geofence_events (dc_id);

CREATE INDEX IF NOT EXISTS ix_lane_miles_dc ON lane_miles (dc_id);

CREATE INDEX IF NOT EXISTS ix_route_trips_dc ON route_trips (dc_id);

CREATE INDEX IF NOT EXISTS ix_route_stops_dc ON route_stops (dc_id);

CREATE INDEX IF NOT EXISTS ix_agent_actions_dc ON agent_actions (dc_id);

CREATE INDEX IF NOT EXISTS ix_inventory_sku ON inventory (sku);

CREATE INDEX IF NOT EXISTS ix_order_lines_sku ON order_lines (sku);

CREATE INDEX IF NOT EXISTS ix_orders_ship ON outbound_orders (dc_id, ship_date);

CREATE INDEX IF NOT EXISTS ix_pick_tasks_wave ON pick_tasks (wave_id);

CREATE INDEX IF NOT EXISTS ix_route_stops_ship ON route_stops (dc_id, ship_date);

CREATE INDEX IF NOT EXISTS ix_geofence_events_time ON geofence_events (dc_id, event_time);
