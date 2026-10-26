#!/usr/bin/env bash
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
SCALE="${1:-1.0}"
python -m warehouse_data.load_sqlite --csv data/csv --db data/wms.db --generate --scale "$SCALE"
for b in sqlite bigquery postgres; do
  out="sql/schema_${b}.sql"; [ "$b" = postgres ] && out="sql/schema_alloydb.sql"
  python - "$b" "$out" <<'PY'
import sys
from warehouse_agent.schema import ddl
b, out = sys.argv[1], sys.argv[2]
open(out, "w").write("-- Generated from warehouse_agent/schema.py. Do not edit by hand.\n"
                     + ddl(b, "mclane_wms" if b == "bigquery" else None))
PY
done
python -m pytest -q
