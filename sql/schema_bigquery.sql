-- Generated from warehouse_agent/schema.py. Do not edit by hand.
CREATE TABLE IF NOT EXISTS `mclane_wms.distribution_centers` (
  dc_id STRING OPTIONS(description="Distribution center code, e.g. MTX"),
  dc_name STRING OPTIONS(description="Display name"),
  city STRING,
  state STRING OPTIONS(description="US state code"),
  segment STRING OPTIONS(description="RETAIL (convenience/grocery) or RESTAURANT (foodservice/QSR)"),
  wms_system STRING OPTIONS(description="MANHATTAN_ACTIVE | BLUE_YONDER | ARGENT"),
  square_feet INT64,
  timezone STRING OPTIONS(description="IANA timezone"),
  latitude FLOAT64 OPTIONS(description="DC yard gate latitude (WGS84)"),
  longitude FLOAT64 OPTIONS(description="DC yard gate longitude (WGS84)")
);

CREATE TABLE IF NOT EXISTS `mclane_wms.items` (
  sku STRING OPTIONS(description="Canonical item id"),
  description STRING,
  category STRING OPTIONS(description="Merchandise category"),
  segment STRING OPTIONS(description="RETAIL | RESTAURANT | BOTH"),
  temp_zone STRING OPTIONS(description="DRY | COOLER | FREEZER"),
  uom STRING OPTIONS(description="Selling unit of measure (CS = case)"),
  case_pack INT64 OPTIONS(description="Eaches per case"),
  case_cube_ft FLOAT64 OPTIONS(description="Cubic feet per case"),
  case_weight_lb FLOAT64,
  unit_cost FLOAT64 OPTIONS(description="Cost per case, USD"),
  shelf_life_days INT64 OPTIONS(description="0 = not date controlled"),
  supplier STRING
);

CREATE TABLE IF NOT EXISTS `mclane_wms.customers` (
  customer_id STRING,
  customer_name STRING OPTIONS(description="Store / restaurant name"),
  chain STRING OPTIONS(description="Banner or brand"),
  segment STRING OPTIONS(description="RETAIL | RESTAURANT"),
  dc_id STRING OPTIONS(description="Servicing DC"),
  route_id STRING OPTIONS(description="Delivery route"),
  city STRING,
  state STRING,
  latitude FLOAT64 OPTIONS(description="Delivery point latitude (WGS84)"),
  longitude FLOAT64 OPTIONS(description="Delivery point longitude (WGS84)"),
  delivery_window_start STRING OPTIONS(description="Receiving window start HH:MM local (restaurant 60 min, retail 120 min)"),
  delivery_window_end STRING OPTIONS(description="Receiving window end HH:MM local"),
  standard_dwell_minutes INT64 OPTIONS(description="Planned on-site time (unload, check-in, put-away for restaurants)")
)
CLUSTER BY dc_id;

CREATE TABLE IF NOT EXISTS `mclane_wms.routes` (
  route_id STRING,
  dc_id STRING,
  departure_time STRING OPTIONS(description="Planned trailer departure HH:MM local"),
  stops INT64 OPTIONS(description="Customers on the route"),
  trailer_type STRING OPTIONS(description="DRY | MULTI_TEMP")
)
CLUSTER BY dc_id;

CREATE TABLE IF NOT EXISTS `mclane_wms.locations` (
  location_id STRING OPTIONS(description="DC-zone-aisle-bay-level"),
  dc_id STRING,
  zone STRING OPTIONS(description="DRY | COOLER | FREEZER"),
  aisle STRING,
  bay INT64,
  level INT64 OPTIONS(description="1 = floor"),
  location_type STRING OPTIONS(description="PICK | RESERVE"),
  is_golden_zone INT64 OPTIONS(description="1 = waist-height pick face near the front of the aisle"),
  capacity_cases INT64,
  distance_to_dock_ft FLOAT64 OPTIONS(description="Travel distance from the shipping dock"),
  pick_sequence INT64 OPTIONS(description="Walk sequence for pick path")
)
CLUSTER BY dc_id;

CREATE TABLE IF NOT EXISTS `mclane_wms.slot_assignments` (
  dc_id STRING,
  location_id STRING OPTIONS(description="PICK location"),
  sku STRING,
  min_qty INT64 OPTIONS(description="Replenishment trigger, cases"),
  max_qty INT64 OPTIONS(description="Replenish-up-to, cases"),
  assigned_date DATE
)
CLUSTER BY dc_id;

CREATE TABLE IF NOT EXISTS `mclane_wms.inventory` (
  inventory_id STRING,
  dc_id STRING,
  location_id STRING,
  sku STRING,
  lot_number STRING,
  qty_on_hand INT64 OPTIONS(description="Cases"),
  qty_allocated INT64 OPTIONS(description="Cases allocated to open orders"),
  status STRING OPTIONS(description="AVAILABLE | HOLD | DAMAGED | QC"),
  received_date DATE,
  expiry_date DATE OPTIONS(description="NULL when not date controlled")
)
CLUSTER BY dc_id;

CREATE TABLE IF NOT EXISTS `mclane_wms.inbound_shipments` (
  asn_id STRING OPTIONS(description="Advance ship notice"),
  dc_id STRING,
  po_number STRING,
  supplier STRING,
  appointment_id STRING,
  expected_date DATE,
  temp_zone STRING,
  pallets INT64,
  cases INT64,
  status STRING OPTIONS(description="SCHEDULED | ARRIVED | RECEIVING | RECEIVED | CANCELLED")
)
CLUSTER BY dc_id;

CREATE TABLE IF NOT EXISTS `mclane_wms.asn_lines` (
  asn_id STRING,
  line_number INT64,
  dc_id STRING,
  sku STRING,
  cases_expected INT64,
  cases_received INT64
)
CLUSTER BY dc_id;

CREATE TABLE IF NOT EXISTS `mclane_wms.outbound_orders` (
  order_id STRING,
  dc_id STRING,
  customer_id STRING,
  route_id STRING,
  order_date DATE,
  ship_date DATE,
  wave_id STRING OPTIONS(description="NULL until waved"),
  status STRING OPTIONS(description="NEW | RELEASED | PICKING | PICKED | LOADED | SHIPPED | CANCELLED"),
  priority INT64 OPTIONS(description="1 = highest"),
  total_lines INT64,
  total_cases INT64
)
CLUSTER BY dc_id;

CREATE TABLE IF NOT EXISTS `mclane_wms.order_lines` (
  order_id STRING,
  line_number INT64,
  dc_id STRING,
  sku STRING,
  qty_ordered INT64 OPTIONS(description="Cases"),
  qty_picked INT64 OPTIONS(description="Cases"),
  qty_short INT64 OPTIONS(description="Cases"),
  short_reason STRING OPTIONS(description="NULL | NO_STOCK | STOCK_ON_HOLD | PICK_FACE_EMPTY | DAMAGED")
)
CLUSTER BY dc_id;

CREATE TABLE IF NOT EXISTS `mclane_wms.waves` (
  wave_id STRING,
  dc_id STRING,
  ship_date DATE,
  wave_type STRING OPTIONS(description="ROUTE | TEMP_ZONE | RUSH"),
  temp_zone STRING,
  released_at DATETIME,
  cutoff_at DATETIME OPTIONS(description="Pick must finish by (trailer departure - load time)"),
  status STRING OPTIONS(description="PLANNED | RELEASED | IN_PROGRESS | COMPLETE"),
  order_count INT64,
  line_count INT64
)
CLUSTER BY dc_id;

CREATE TABLE IF NOT EXISTS `mclane_wms.pick_tasks` (
  task_id STRING,
  dc_id STRING,
  wave_id STRING,
  order_id STRING,
  line_number INT64,
  sku STRING,
  location_id STRING,
  qty INT64 OPTIONS(description="Cases to pick"),
  qty_picked INT64,
  associate_id STRING,
  status STRING OPTIONS(description="OPEN | ASSIGNED | IN_PROGRESS | COMPLETE | SHORT"),
  created_at DATETIME,
  completed_at DATETIME,
  travel_ft FLOAT64 OPTIONS(description="Round-trip travel for this task")
)
CLUSTER BY dc_id;

CREATE TABLE IF NOT EXISTS `mclane_wms.associates` (
  associate_id STRING,
  dc_id STRING,
  associate_name STRING,
  role STRING OPTIONS(description="PICKER | LOADER | RECEIVER | FORKLIFT"),
  home_zone STRING OPTIONS(description="DRY | COOLER | FREEZER"),
  shift STRING OPTIONS(description="DAY | NIGHT"),
  hire_date DATE,
  hourly_rate FLOAT64 OPTIONS(description="USD")
)
CLUSTER BY dc_id;

CREATE TABLE IF NOT EXISTS `mclane_wms.labor_standards` (
  role STRING,
  zone STRING,
  engineered_rate FLOAT64 OPTIONS(description="Cases per hour at 100% performance")
);

CREATE TABLE IF NOT EXISTS `mclane_wms.labor_activity` (
  activity_id STRING,
  dc_id STRING,
  associate_id STRING,
  work_date DATE,
  role STRING,
  zone STRING,
  cases_handled INT64,
  direct_hours FLOAT64,
  indirect_hours FLOAT64 OPTIONS(description="Meetings, travel to zone, equipment issues")
)
CLUSTER BY dc_id;

CREATE TABLE IF NOT EXISTS `mclane_wms.labor_schedule` (
  dc_id STRING,
  associate_id STRING,
  work_date DATE,
  shift STRING,
  scheduled_hours FLOAT64,
  status STRING OPTIONS(description="SCHEDULED | PTO | CALLOUT")
)
CLUSTER BY dc_id;

CREATE TABLE IF NOT EXISTS `mclane_wms.dock_doors` (
  door_id STRING,
  dc_id STRING,
  door_type STRING OPTIONS(description="INBOUND | OUTBOUND"),
  temp_capable INT64 OPTIONS(description="1 = refrigerated seal / reefer plug")
)
CLUSTER BY dc_id;

CREATE TABLE IF NOT EXISTS `mclane_wms.dock_appointments` (
  appointment_id STRING,
  dc_id STRING,
  door_id STRING,
  direction STRING OPTIONS(description="INBOUND | OUTBOUND"),
  carrier STRING,
  reference_id STRING OPTIONS(description="ASN id (inbound) or route id (outbound)"),
  temp_zone STRING OPTIONS(description="Most restrictive temp zone on the trailer"),
  scheduled_start DATETIME,
  scheduled_end DATETIME,
  actual_arrival DATETIME OPTIONS(description="NULL = not arrived"),
  door_assigned_at DATETIME,
  completed_at DATETIME,
  status STRING OPTIONS(description="SCHEDULED | CHECKED_IN | AT_DOOR | COMPLETED | NO_SHOW")
)
CLUSTER BY dc_id;

CREATE TABLE IF NOT EXISTS `mclane_wms.cycle_counts` (
  count_id STRING,
  dc_id STRING,
  location_id STRING,
  sku STRING,
  count_date DATE,
  system_qty INT64,
  counted_qty INT64,
  variance_qty INT64 OPTIONS(description="counted - system"),
  variance_value FLOAT64 OPTIONS(description="USD"),
  counter_id STRING
)
CLUSTER BY dc_id;

CREATE TABLE IF NOT EXISTS `mclane_wms.wms_integration_events` (
  event_id STRING,
  dc_id STRING,
  source_system STRING OPTIONS(description="MANHATTAN_ACTIVE | BLUE_YONDER | ARGENT"),
  interface STRING OPTIONS(description="Canonical interface, e.g. ITEM_MASTER, ASN, ORDER_RELEASE, SHIP_CONFIRM"),
  source_message_type STRING OPTIONS(description="Source-native message name (illustrative)"),
  event_time DATETIME,
  status STRING OPTIONS(description="SUCCESS | ERROR | RETRY"),
  error_code STRING,
  error_detail STRING,
  reference_id STRING OPTIONS(description="Order, ASN or SKU the message is about")
)
CLUSTER BY dc_id;

CREATE TABLE IF NOT EXISTS `mclane_wms.wms_field_map` (
  source_system STRING,
  source_entity STRING,
  source_field STRING OPTIONS(description="Illustrative source-native name"),
  canonical_table STRING,
  canonical_field STRING,
  transform_rule STRING
);

CREATE TABLE IF NOT EXISTS `mclane_wms.geofences` (
  geofence_id STRING OPTIONS(description="GF-<site id>"),
  dc_id STRING OPTIONS(description="Owning / servicing DC"),
  site_type STRING OPTIONS(description="DC_YARD | CUSTOMER"),
  site_id STRING OPTIONS(description="dc_id or customer_id"),
  name STRING,
  latitude FLOAT64 OPTIONS(description="Circle center"),
  longitude FLOAT64 OPTIONS(description="Circle center"),
  radius_m INT64 OPTIONS(description="Circle radius in meters")
)
CLUSTER BY dc_id;

CREATE TABLE IF NOT EXISTS `mclane_wms.geofence_events` (
  event_id STRING OPTIONS(description="Telematics event id"),
  dc_id STRING,
  geofence_id STRING,
  site_type STRING OPTIONS(description="DC_YARD | CUSTOMER"),
  site_id STRING OPTIONS(description="dc_id or customer_id"),
  asset_id STRING OPTIONS(description="Trailer / tractor id from the telematics unit"),
  carrier STRING,
  reference_type STRING OPTIONS(description="APPOINTMENT (inbound trailer) | TRIP (McLane route)"),
  reference_id STRING OPTIONS(description="appointment_id or trip_id"),
  event_type STRING OPTIONS(description="ENTER | EXIT"),
  event_time DATETIME OPTIONS(description="Local time"),
  latitude FLOAT64 OPTIONS(description="Ping position"),
  longitude FLOAT64 OPTIONS(description="Ping position")
)
CLUSTER BY dc_id;

CREATE TABLE IF NOT EXISTS `mclane_wms.lane_miles` (
  origin_id STRING OPTIONS(description="dc_id or customer_id"),
  dest_id STRING OPTIONS(description="dc_id or customer_id"),
  dc_id STRING,
  practical_miles FLOAT64 OPTIONS(description="PC*MILER practical route miles (truck)"),
  shortest_miles FLOAT64 OPTIONS(description="PC*MILER shortest route miles"),
  drive_minutes INT64 OPTIONS(description="PC*MILER drive time"),
  source STRING OPTIONS(description="PCMILER_SYNTH (demo) | PCMILER_API | PCMILER_BATCH"),
  computed_date DATE
)
CLUSTER BY dc_id;

CREATE TABLE IF NOT EXISTS `mclane_wms.route_trips` (
  trip_id STRING OPTIONS(description="One trailer run of a route on a ship date"),
  dc_id STRING,
  route_id STRING,
  ship_date DATE,
  segment STRING OPTIONS(description="RETAIL | RESTAURANT"),
  tractor_id STRING,
  planned_departure DATETIME,
  actual_departure DATETIME OPTIONS(description="DC yard geofence EXIT; NULL = not departed"),
  departure_delay_minutes INT64,
  delay_reason STRING OPTIONS(description="NULL | LATE_WAVE | LATE_LOAD | DRIVER | EQUIPMENT"),
  planned_miles FLOAT64 OPTIONS(description="PC*MILER practical miles, DC -> stops -> DC"),
  actual_miles FLOAT64 OPTIONS(description="Odometer / telematics miles"),
  stops_planned INT64,
  stops_completed INT64,
  returned_at DATETIME OPTIONS(description="DC yard geofence ENTER on return"),
  status STRING OPTIONS(description="PLANNED | IN_TRANSIT | COMPLETED")
)
CLUSTER BY dc_id;

CREATE TABLE IF NOT EXISTS `mclane_wms.route_stops` (
  stop_id STRING,
  trip_id STRING,
  dc_id STRING,
  route_id STRING,
  ship_date DATE,
  stop_seq INT64,
  customer_id STRING,
  segment STRING OPTIONS(description="RETAIL | RESTAURANT"),
  order_id STRING,
  miles_from_prev FLOAT64 OPTIONS(description="PC*MILER practical miles from the previous stop (or DC)"),
  window_start DATETIME OPTIONS(description="Customer receiving window"),
  window_end DATETIME,
  planned_arrival DATETIME,
  eta DATETIME OPTIONS(description="Telematics ETA for stops not reached yet"),
  actual_arrival DATETIME OPTIONS(description="Customer geofence ENTER"),
  actual_departure DATETIME OPTIONS(description="Customer geofence EXIT"),
  dwell_minutes INT64 OPTIONS(description="actual_departure - actual_arrival"),
  standard_dwell_minutes INT64,
  on_time INT64 OPTIONS(description="1 = arrived by window_end (OTD); NULL until delivered"),
  late_minutes INT64,
  late_reason STRING OPTIONS(description="NULL | LATE_DEPARTURE | CUSTOMER_DWELL | TRAFFIC | ROUTE_PLAN"),
  status STRING OPTIONS(description="PLANNED | EN_ROUTE | AT_STOP | DELIVERED")
)
CLUSTER BY dc_id;

CREATE TABLE IF NOT EXISTS `mclane_wms.agent_actions` (
  action_id STRING,
  created_at DATETIME,
  dc_id STRING,
  action_type STRING OPTIONS(description="REPLENISH | RESLOT | REASSIGN_DOOR | RELEASE_WAVE | REBALANCE_LABOR | CYCLE_COUNT | RESEQUENCE_ROUTE | NOTIFY_CUSTOMER | OTHER"),
  details STRING OPTIONS(description="JSON payload"),
  rationale STRING,
  status STRING OPTIONS(description="PROPOSED | APPROVED | REJECTED"),
  decided_at DATETIME
)
CLUSTER BY dc_id;
