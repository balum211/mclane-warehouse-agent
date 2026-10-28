# Implementation Plan: McLane delivery view

**Branch**: `002-delivery-otd-geofence` | **Spec**: [spec.md](spec.md)

## Technical context
Python 3.12, Google ADK, same backends (SQLite / BigQuery / AlloyDB / Cloud SQL). No new runtime
dependencies: the PC*MILER client uses `urllib`.

## Constitution check
- Grounded, quantified: every tool returns counts, minutes, miles and its source. ✓
- Hard constraints: delivery tools never override food safety (prompt rule). ✓
- Human in the loop: RESEQUENCE_ROUTE / NOTIFY_CUSTOMER via `propose_action`. ✓
- Portable SQL: time windows computed in Python, DuckDB test covers the new tools. ✓
- Test before demo: `tests/test_delivery.py`, flow test for the new agent and collectors. ✓

## Design
- Schema: `geofences`, `geofence_events`, `lane_miles`, `route_trips`, `route_stops`; geo, window and
  standard dwell columns on `customers` / `distribution_centers` ([data-model.md](data-model.md)).
- Generator: `warehouse_data/delivery.py` `DeliveryBuilder` runs after `Gen` with `Random(seed + 101)`:
  customers placed in a compass sector per route (radius 8-150 mi retail, 4-110 mi restaurant),
  nearest-neighbour stop order by PC*MILER miles, windows set from each customer's planned arrivals
  (p90 + 10 min), drive noise +/-6%, dwell noise +/-15%, 11 days of extra inbound history for yard
  dwell baselines.
- `warehouse_agent/pcmiler.py`: haversine, destination point, deterministic circuity, drive-time
  model (27 mph first 10 mi, 47 mph after), Web Services client.
- Tools (`tools/delivery.py`): `get_otd_performance`, `get_route_status`, `assess_route_otd_risk`
  (reuses `recommend_wave_release`), `get_dwell_time_changes`, `get_geofence_activity`,
  `get_route_miles`, `lookup_customer_site`.
- Agents: `delivery_otd_agent`; `delivery_snapshot_agent` in `briefing_collectors`;
  `replan_otd_agent` in `replan_assessors`; writer prompts gain Delivery sections.
- MCP Toolbox: `otd-by-segment`, `inbound-yard-dwell-by-carrier`, `pcmiler-lane-miles`.

## Project structure (new / changed)
```text
warehouse_agent/pcmiler.py, tools/delivery.py, schema.py, agent.py, prompts.py, tools/actions.py
warehouse_data/delivery.py, generate.py
tests/test_delivery.py, test_portability.py, test_agent_flow.py
.agents/skills/mclane-otd-dwell/
```
