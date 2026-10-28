#!/usr/bin/env bash
# Regenerate CSVs + SQLite, re-render sql/schema_*.sql and docs/DATA_MODEL.md, then run the tests.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
SCALE="${1:-1.0}"
python -m warehouse_data.load_sqlite --csv data/csv --db data/wms.db --generate --scale "$SCALE"
python scripts/render_schema_docs.py
python -m pytest -q
