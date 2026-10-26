---
name: wms-synthetic-data
description: Use when regenerating, extending or reshaping the synthetic McLane WMS dataset (new tables, more DCs, different volumes, new planted scenarios), or when loading it into SQLite, BigQuery or AlloyDB.
---

# Synthetic WMS data

## Facts
- Generator: `warehouse_data/generate.py` (deterministic, seed 27, anchor 2026-10-27 10:30).
- Schema: `warehouse_agent/schema.py` is the single source of truth; `sql/schema_*.sql` are rendered from it.
- Loaders: `warehouse_data/load_sqlite.py`, `load_bigquery.py`, `load_alloydb.py`.
- Default volume: 6 DCs, 500 SKUs, ~6,200 locations, ~100k order lines, ~240k rows total.

## Regenerate
`bash .agents/skills/wms-synthetic-data/scripts/regen.sh [scale]` regenerates CSVs + SQLite,
re-renders the DDL files and runs the tests. `scale` (default 1.0) multiplies SKUs and customers.

## Extending
1. Add the table/columns to `schema.py` (and `PRIMARY_KEYS`).
2. Generate rows in a `build_*` method of `Gen`, called from `run()` in dependency order
   (masters -> network -> facility -> orders -> inventory -> labor -> dock -> counts -> integration).
3. Keep it deterministic: only use `self.r` for randomness.
4. Plant scenarios explicitly and document them in the module docstring and
   `.agents/rules/project-context.md`; guard each with a test in `tests/test_tools.py`.
5. Names must stay fictional; source-system message and field names are illustrative.

## Load to cloud
- BigQuery: `make bq-load PROJECT=<id>` (dataset `mclane_wms`, clustered by `dc_id`).
- AlloyDB: `bash deploy/setup_alloydb.sh` then `make alloydb-load`.
