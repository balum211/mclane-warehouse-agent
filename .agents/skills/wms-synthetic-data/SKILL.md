---
name: wms-synthetic-data
description: Use when regenerating, extending or reshaping the synthetic McLane WMS dataset (new tables, more DCs, different volumes, new planted scenarios), or when loading it into SQLite, BigQuery, AlloyDB or Cloud SQL for PostgreSQL. Covers the delivery data too (geofences, PC*MILER lane miles, route trips and stops, OTD, dwell).
---

# Synthetic WMS data

## Facts
- Generator: `warehouse_data/generate.py` (deterministic, seed 27, anchor 2026-10-27 10:30) plus
  `warehouse_data/delivery.py` (geo, PC*MILER lanes, trips / stops, geofence events) on its own random
  stream (`seed + 101`) so delivery changes never move the warehouse demo numbers.
- Schema: `warehouse_agent/schema.py` is the single source of truth (28 tables); `sql/schema_*.sql` and
  `docs/DATA_MODEL.md` are rendered from it by `python scripts/render_schema_docs.py`.
- Loaders: `warehouse_data/load_sqlite.py`, `load_bigquery.py`, `load_postgres.py`
  (`--target alloydb|cloudsql|postgres`; `load_alloydb.py` is kept as an alias).
- Default volume: 6 DCs, 500 SKUs, 7,800 locations, ~100k order lines, ~7k route stops, ~17k geofence
  events, ~277k rows total.

## Regenerate
`bash .agents/skills/wms-synthetic-data/scripts/regen.sh [scale]` regenerates CSVs + SQLite,
re-renders the DDL files and runs the tests. `scale` (default 1.0) multiplies SKUs and customers.

## Extending
1. Add the table/columns to `schema.py` (and `PRIMARY_KEYS`).
2. Generate rows in a `build_*` method of `Gen`, called from `run()` in dependency order
   (masters -> network -> facility -> orders -> inventory -> labor -> dock -> counts -> integration).
3. Keep it deterministic: only use `self.r` for randomness in `Gen`, and `DeliveryBuilder.r` for
   delivery data. Never draw from `self.r` after the warehouse build or the demo numbers shift.
4. Plant scenarios explicitly and document them in the module docstring and
   `.agents/rules/project-context.md`; guard each with a test in `tests/test_tools.py`.
5. Names must stay fictional; source-system message and field names are illustrative.

## Load to cloud
- BigQuery: `make bq-load PROJECT=<id>` (dataset `mclane_wms`, clustered by `dc_id`).
- AlloyDB: `bash deploy/setup_alloydb.sh` then `make alloydb-load`.
- Cloud SQL (e.g. the sdd-adk-agents-agy `restaurant-db` instance): `bash deploy/setup_cloudsql.sh`
  or `make cloudsql-load` with `CLOUD_SQL_INSTANCE` and `DB_PASSWORD` set.
