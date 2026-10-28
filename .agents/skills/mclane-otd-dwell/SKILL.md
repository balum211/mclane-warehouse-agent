---
name: mclane-otd-dwell
description: Use when a question or code change involves McLane delivery metrics - on-time delivery (OTD) for Retail vs Restaurant, dwell time changes (DC yard or customer stop), geofences / telematics events, geolocations, receiving windows, or PC*MILER miles - so definitions, tables and tools stay consistent.
---

# McLane OTD, dwell, geofence and PC*MILER

## Definitions (keep these exact; prompts, tools and tests depend on them)
- **OTD**: a stop is on time when the truck's customer geofence ENTER is at or before
  `route_stops.window_end`. Restaurant windows are 60 minutes, retail (c-store) 120 minutes. Report
  Retail and Restaurant separately; never blend them into one number without also giving both.
- **Late reason** (first match): `ROUTE_PLAN` (planned arrival already after window end),
  `LATE_DEPARTURE` (trailer left the DC 20+ min late), `CUSTOMER_DWELL` (extra minutes at earlier
  stops exceed extra drive minutes), else `TRAFFIC`.
- **Inbound yard dwell**: DC yard geofence ENTER to EXIT for an inbound appointment, split into
  gate-to-door (`actual_arrival` -> `door_assigned_at`), unload (-> `completed_at`) and door-to-gate
  (-> EXIT). Over 120 minutes in the yard means detention risk.
- **Customer dwell**: customer geofence ENTER to EXIT (`route_stops.dwell_minutes`) against
  `customers.standard_dwell_minutes` (retail ~22, restaurant ~35: drivers stock the walk-in).
- **Dwell change**: current period (default 7 days ending now) vs the prior period of equal length.
- **PC*MILER miles**: practical miles by default. Source order: PC*MILER Web Services
  (`PCMILER_API_KEY`) -> `lane_miles` table (PC*MILER batch export; `PCMILER_SYNTH` in the demo) ->
  `ESTIMATE` (great circle x 1.17-1.30 circuity). Always state the source.

## Where things live
- Tables: `geofences`, `geofence_events`, `lane_miles`, `route_trips`, `route_stops`, plus geo /
  window / standard dwell columns on `customers` and `distribution_centers` (see `docs/DATA_MODEL.md`).
- Generator: `warehouse_data/delivery.py` (own random stream; planted scenarios in its docstring).
- PC*MILER client and geo helpers: `warehouse_agent/pcmiler.py`.
- Tools: `warehouse_agent/tools/delivery.py` -> `get_otd_performance`, `get_route_status`,
  `assess_route_otd_risk`, `get_dwell_time_changes`, `get_geofence_activity`, `get_route_miles`,
  `lookup_customer_site`. Agent: `delivery_otd_agent`; collectors `delivery_snapshot_agent`
  (briefing) and `replan_otd_agent` (re-plan).
- Tests: `tests/test_delivery.py` guards every planted delivery scenario.

## Planted demo facts (seed 27, clock 2026-10-27 10:30)
Print them with `python .agents/skills/wms-demo-facts/scripts/demo_facts.py MTX` (delivery section).
FDL restaurant OTD 68.0% vs 86.9% prior (LATE_DEPARTURE); MTX-R07 chronically late (TRAFFIC);
Taco Trail (FDL) dwell up about 22 min; Lonestar at MTX yard dwell up about 59 min; Swift Haul
trailer in the MTX yard geofence, not checked in; tomorrow 41 of 86 MTX stops miss windows with 2
pickers and 0 with 5.

## When adding a delivery metric
1. Put the definition in `references/metrics.md` first, then in the tool docstring.
2. Follow the `wms-portable-sql` skill (compute time windows in Python, no SQL date math).
3. Add the planted scenario to `delivery.py` using `self.r` only, and a test in `tests/test_delivery.py`.
4. Re-render docs with `python scripts/render_schema_docs.py` if the schema changed.
