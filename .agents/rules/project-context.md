# Project context: McLane Warehouse Operations Copilot

## Business
McLane distributes to convenience retail (grocery DCs) and restaurant / QSR chains (foodservice
DCs). Buildings run one of three WMS platforms: Manhattan Active WM, Blue Yonder WMS or Argent.
Night shift (18:00-02:30) picks tomorrow's routes; trailers leave 03:00-08:30. Temperature zones:
DRY, COOLER, FREEZER. Users: DC managers, shift supervisors, inventory control, dock leads.

## Data
- One canonical schema (`warehouse_agent/schema.py`, 23 tables) harmonizes all three WMS platforms.
  `distribution_centers.wms_system` says which platform owns a DC; `wms_field_map` maps source fields.
- Synthetic data is deterministic (seed 27) and anchored to **2026-10-27 10:30** (`WMS_AS_OF_DATE`,
  `WMS_CLOCK`). Six DCs: MTX, MGA (Manhattan Active), MCA, MNY (Blue Yonder), FDL, FOH (Argent).
- Planted scenarios the demo relies on (don't break them; `tests/test_tools.py` guards them):
  MTX night-shift call-outs (labor SHORT), a late inbound trailer carrying SKUs tonight's orders
  need, a freezer load on a dry door, a double-booked door, a detention-risk trailer, expired and
  short-dated lots, pick faces below min, mis-slotted fast movers, a Blue Yonder UOM_MISMATCH spike
  at MCA, negative on-hand / over-capacity / cold-product-in-ambient anomalies.

## Architecture
- `warehouse_ops_orchestrator` (LlmAgent) routes to 7 specialists (inventory, slotting,
  fulfillment, labor, dock_yard, wms_integration, data_analyst) and two pipelines
  (`shift_briefing_pipeline`, `disruption_replan_pipeline`: SequentialAgent of a ParallelAgent of
  collectors + a writer that reads their `output_key`s from session state).
- Backends: `WMS_DB_BACKEND=sqlite|bigquery|alloydb`. Tools write SQL once with `{table}`
  placeholders and `:param` binds; `db.py` adapts it.

## Conventions
- Python 3.11+, type hints, Google-style docstrings (ADK builds tool schemas from them).
- Tool args are simple types with defaults; DC-scoped tools take `dc_id` first.
- No secrets in code; config via `warehouse_agent/.env` (see `.env.example`).
