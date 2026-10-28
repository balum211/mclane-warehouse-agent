# Delivery metric formulas

| Metric | Formula | Columns |
|---|---|---|
| OTD % | on-time stops / delivered stops x 100 | `route_stops.on_time` (1/0), `ship_date`, `segment` |
| Avg minutes late | mean of `late_minutes` over late stops | `route_stops.late_minutes` |
| On-time departure % | trips with `departure_delay_minutes` < 20 / departed trips | `route_trips` |
| Inbound yard dwell (min) | EXIT `event_time` - ENTER `event_time` per appointment | `geofence_events` (`site_type`='DC_YARD', `reference_type`='APPOINTMENT') |
| Gate-to-door (min) | `door_assigned_at` - `actual_arrival` | `dock_appointments` |
| Unload (min) | `completed_at` - `door_assigned_at` | `dock_appointments` |
| Door-to-gate (min) | yard EXIT - `completed_at` | `geofence_events`, `dock_appointments` |
| Detention risk | in yard > 120 min and not at a door | `geofence_events`, `dock_appointments.status` |
| Customer dwell (min) | `actual_departure` - `actual_arrival` | `route_stops.dwell_minutes` |
| Dwell vs standard | `dwell_minutes` - `standard_dwell_minutes` | `route_stops` |
| Planned vs actual miles | `actual_miles` / `planned_miles` - 1 | `route_trips` (PC*MILER planned) |
| Stops at risk (tomorrow) | planned arrival + projected departure delay > window end | `route_stops`, waves via `outbound_orders.wave_id` |
