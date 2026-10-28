# Data model: delivery view

Full column lists: [docs/DATA_MODEL.md](../../docs/DATA_MODEL.md) ("Delivery, geofences and PC*MILER").

| Table | Grain | Key columns |
|---|---|---|
| `geofences` | one circle per DC yard / customer | `geofence_id`, `site_type`, `site_id`, `latitude`, `longitude`, `radius_m` |
| `geofence_events` | one telematics ENTER or EXIT | `asset_id`, `reference_type` (APPOINTMENT / TRIP), `reference_id`, `event_type`, `event_time` |
| `lane_miles` | one directed lane | `origin_id`, `dest_id`, `practical_miles`, `shortest_miles`, `drive_minutes`, `source` |
| `route_trips` | one route run per ship date | `planned_departure`, `actual_departure`, `departure_delay_minutes`, `delay_reason`, `planned_miles` |
| `route_stops` | one customer stop (one order) | `window_start/end`, `planned_arrival`, `eta`, `actual_arrival/departure`, `dwell_minutes`, `on_time`, `late_reason` |

Added columns: `customers.latitude, longitude, delivery_window_start, delivery_window_end,
standard_dwell_minutes`; `distribution_centers.latitude, longitude`.

Relationships: `route_stops.order_id` -> `outbound_orders`; `route_stops.trip_id` -> `route_trips`;
`geofence_events.reference_id` -> `dock_appointments.appointment_id` or `route_trips.trip_id`;
`geofences.site_id` -> `customers.customer_id` or `distribution_centers.dc_id`.
