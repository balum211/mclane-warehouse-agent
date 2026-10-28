-- Generated from warehouse_agent/schema.py. Do not edit by hand.
CREATE TABLE IF NOT EXISTS distribution_centers (
  dc_id TEXT,
  dc_name TEXT,
  city TEXT,
  state TEXT,
  segment TEXT,
  wms_system TEXT,
  square_feet BIGINT,
  timezone TEXT,
  latitude DOUBLE PRECISION,
  longitude DOUBLE PRECISION,
  PRIMARY KEY (dc_id)
);

CREATE TABLE IF NOT EXISTS items (
  sku TEXT,
  description TEXT,
  category TEXT,
  segment TEXT,
  temp_zone TEXT,
  uom TEXT,
  case_pack BIGINT,
  case_cube_ft DOUBLE PRECISION,
  case_weight_lb DOUBLE PRECISION,
  unit_cost DOUBLE PRECISION,
  shelf_life_days BIGINT,
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
  latitude DOUBLE PRECISION,
  longitude DOUBLE PRECISION,
  delivery_window_start TEXT,
  delivery_window_end TEXT,
  standard_dwell_minutes BIGINT,
  PRIMARY KEY (customer_id)
);

CREATE TABLE IF NOT EXISTS routes (
  route_id TEXT,
  dc_id TEXT,
  departure_time TEXT,
  stops BIGINT,
  trailer_type TEXT,
  PRIMARY KEY (route_id)
);

CREATE TABLE IF NOT EXISTS locations (
  location_id TEXT,
  dc_id TEXT,
  zone TEXT,
  aisle TEXT,
  bay BIGINT,
  level BIGINT,
  location_type TEXT,
  is_golden_zone BIGINT,
  capacity_cases BIGINT,
  distance_to_dock_ft DOUBLE PRECISION,
  pick_sequence BIGINT,
  PRIMARY KEY (location_id)
);

CREATE TABLE IF NOT EXISTS slot_assignments (
  dc_id TEXT,
  location_id TEXT,
  sku TEXT,
  min_qty BIGINT,
  max_qty BIGINT,
  assigned_date DATE,
  PRIMARY KEY (location_id)
);

CREATE TABLE IF NOT EXISTS inventory (
  inventory_id TEXT,
  dc_id TEXT,
  location_id TEXT,
  sku TEXT,
  lot_number TEXT,
  qty_on_hand BIGINT,
  qty_allocated BIGINT,
  status TEXT,
  received_date DATE,
  expiry_date DATE,
  PRIMARY KEY (inventory_id)
);

CREATE TABLE IF NOT EXISTS inbound_shipments (
  asn_id TEXT,
  dc_id TEXT,
  po_number TEXT,
  supplier TEXT,
  appointment_id TEXT,
  expected_date DATE,
  temp_zone TEXT,
  pallets BIGINT,
  cases BIGINT,
  status TEXT,
  PRIMARY KEY (asn_id)
);

CREATE TABLE IF NOT EXISTS asn_lines (
  asn_id TEXT,
  line_number BIGINT,
  dc_id TEXT,
  sku TEXT,
  cases_expected BIGINT,
  cases_received BIGINT,
  PRIMARY KEY (asn_id, line_number)
);

CREATE TABLE IF NOT EXISTS outbound_orders (
  order_id TEXT,
  dc_id TEXT,
  customer_id TEXT,
  route_id TEXT,
  order_date DATE,
  ship_date DATE,
  wave_id TEXT,
  status TEXT,
  priority BIGINT,
  total_lines BIGINT,
  total_cases BIGINT,
  PRIMARY KEY (order_id)
);

CREATE TABLE IF NOT EXISTS order_lines (
  order_id TEXT,
  line_number BIGINT,
  dc_id TEXT,
  sku TEXT,
  qty_ordered BIGINT,
  qty_picked BIGINT,
  qty_short BIGINT,
  short_reason TEXT,
  PRIMARY KEY (order_id, line_number)
);

CREATE TABLE IF NOT EXISTS waves (
  wave_id TEXT,
  dc_id TEXT,
  ship_date DATE,
  wave_type TEXT,
  temp_zone TEXT,
  released_at TIMESTAMP,
  cutoff_at TIMESTAMP,
  status TEXT,
  order_count BIGINT,
  line_count BIGINT,
  PRIMARY KEY (wave_id)
);

CREATE TABLE IF NOT EXISTS pick_tasks (
  task_id TEXT,
  dc_id TEXT,
  wave_id TEXT,
  order_id TEXT,
  line_number BIGINT,
  sku TEXT,
  location_id TEXT,
  qty BIGINT,
  qty_picked BIGINT,
  associate_id TEXT,
  status TEXT,
  created_at TIMESTAMP,
  completed_at TIMESTAMP,
  travel_ft DOUBLE PRECISION,
  PRIMARY KEY (task_id)
);

CREATE TABLE IF NOT EXISTS associates (
  associate_id TEXT,
  dc_id TEXT,
  associate_name TEXT,
  role TEXT,
  home_zone TEXT,
  shift TEXT,
  hire_date DATE,
  hourly_rate DOUBLE PRECISION,
  PRIMARY KEY (associate_id)
);

CREATE TABLE IF NOT EXISTS labor_standards (
  role TEXT,
  zone TEXT,
  engineered_rate DOUBLE PRECISION,
  PRIMARY KEY (role, zone)
);

CREATE TABLE IF NOT EXISTS labor_activity (
  activity_id TEXT,
  dc_id TEXT,
  associate_id TEXT,
  work_date DATE,
  role TEXT,
  zone TEXT,
  cases_handled BIGINT,
  direct_hours DOUBLE PRECISION,
  indirect_hours DOUBLE PRECISION,
  PRIMARY KEY (activity_id)
);

CREATE TABLE IF NOT EXISTS labor_schedule (
  dc_id TEXT,
  associate_id TEXT,
  work_date DATE,
  shift TEXT,
  scheduled_hours DOUBLE PRECISION,
  status TEXT,
  PRIMARY KEY (associate_id, work_date)
);

CREATE TABLE IF NOT EXISTS dock_doors (
  door_id TEXT,
  dc_id TEXT,
  door_type TEXT,
  temp_capable BIGINT,
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
  scheduled_start TIMESTAMP,
  scheduled_end TIMESTAMP,
  actual_arrival TIMESTAMP,
  door_assigned_at TIMESTAMP,
  completed_at TIMESTAMP,
  status TEXT,
  PRIMARY KEY (appointment_id)
);

CREATE TABLE IF NOT EXISTS cycle_counts (
  count_id TEXT,
  dc_id TEXT,
  location_id TEXT,
  sku TEXT,
  count_date DATE,
  system_qty BIGINT,
  counted_qty BIGINT,
  variance_qty BIGINT,
  variance_value DOUBLE PRECISION,
  counter_id TEXT,
  PRIMARY KEY (count_id)
);

CREATE TABLE IF NOT EXISTS wms_integration_events (
  event_id TEXT,
  dc_id TEXT,
  source_system TEXT,
  interface TEXT,
  source_message_type TEXT,
  event_time TIMESTAMP,
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
  latitude DOUBLE PRECISION,
  longitude DOUBLE PRECISION,
  radius_m BIGINT,
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
  event_time TIMESTAMP,
  latitude DOUBLE PRECISION,
  longitude DOUBLE PRECISION,
  PRIMARY KEY (event_id)
);

CREATE TABLE IF NOT EXISTS lane_miles (
  origin_id TEXT,
  dest_id TEXT,
  dc_id TEXT,
  practical_miles DOUBLE PRECISION,
  shortest_miles DOUBLE PRECISION,
  drive_minutes BIGINT,
  source TEXT,
  computed_date DATE,
  PRIMARY KEY (origin_id, dest_id)
);

CREATE TABLE IF NOT EXISTS route_trips (
  trip_id TEXT,
  dc_id TEXT,
  route_id TEXT,
  ship_date DATE,
  segment TEXT,
  tractor_id TEXT,
  planned_departure TIMESTAMP,
  actual_departure TIMESTAMP,
  departure_delay_minutes BIGINT,
  delay_reason TEXT,
  planned_miles DOUBLE PRECISION,
  actual_miles DOUBLE PRECISION,
  stops_planned BIGINT,
  stops_completed BIGINT,
  returned_at TIMESTAMP,
  status TEXT,
  PRIMARY KEY (trip_id)
);

CREATE TABLE IF NOT EXISTS route_stops (
  stop_id TEXT,
  trip_id TEXT,
  dc_id TEXT,
  route_id TEXT,
  ship_date DATE,
  stop_seq BIGINT,
  customer_id TEXT,
  segment TEXT,
  order_id TEXT,
  miles_from_prev DOUBLE PRECISION,
  window_start TIMESTAMP,
  window_end TIMESTAMP,
  planned_arrival TIMESTAMP,
  eta TIMESTAMP,
  actual_arrival TIMESTAMP,
  actual_departure TIMESTAMP,
  dwell_minutes BIGINT,
  standard_dwell_minutes BIGINT,
  on_time BIGINT,
  late_minutes BIGINT,
  late_reason TEXT,
  status TEXT,
  PRIMARY KEY (stop_id)
);

CREATE TABLE IF NOT EXISTS agent_actions (
  action_id TEXT,
  created_at TIMESTAMP,
  dc_id TEXT,
  action_type TEXT,
  details TEXT,
  rationale TEXT,
  status TEXT,
  decided_at TIMESTAMP,
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
