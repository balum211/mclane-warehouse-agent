"""Generate (optionally) and load the synthetic WMS data into a local SQLite file.

    python -m warehouse_data.load_sqlite --csv data/csv --db data/wms.db --generate
"""

from __future__ import annotations

import argparse
import csv
import sqlite3
from pathlib import Path

from warehouse_data.generate import DEFAULT_AS_OF, generate
from warehouse_data.schema import TABLES, ddl

_CAST = {"INT": int, "FLOAT": float}


def load(csv_dir: Path, db_path: Path) -> dict[str, int]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    conn = sqlite3.connect(db_path)
    conn.executescript(ddl("sqlite"))
    counts = {}
    for table, cols in TABLES.items():
        names = [c[0] for c in cols]
        casts = [_CAST.get(c[1]) for c in cols]
        with open(csv_dir / f"{table}.csv", newline="", encoding="utf-8") as f:
            rows = []
            for rec in csv.DictReader(f):
                row = []
                for name, cast in zip(names, casts):
                    v = rec[name]
                    row.append(None if v == "" else (cast(v) if cast else v))
                rows.append(row)
        conn.executemany(f"INSERT INTO {table} ({', '.join(names)}) VALUES ({', '.join('?' * len(names))})", rows)
        counts[table] = len(rows)
    conn.commit()
    conn.close()
    return counts


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--csv", default="data/csv", type=Path)
    p.add_argument("--db", default="data/wms.db", type=Path)
    p.add_argument("--generate", action="store_true", help="Regenerate CSVs first")
    p.add_argument("--scale", default=1.0, type=float)
    p.add_argument("--as-of", default=DEFAULT_AS_OF.isoformat())
    a = p.parse_args()
    if a.generate or not (a.csv / "items.csv").exists():
        from datetime import date

        generate(a.csv, date.fromisoformat(a.as_of), a.scale)
    counts = load(a.csv, a.db)
    print(f"Loaded {sum(counts.values()):,} rows into {a.db}")


if __name__ == "__main__":
    main()
