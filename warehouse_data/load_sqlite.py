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


def build_sqlite(db_path: Path, scale: float = 1.0) -> dict[str, int]:
    """Generate the dataset and load it into db_path (used for first-run auto-generation)."""
    import os
    from datetime import date

    as_of = date.fromisoformat(os.environ.get("WMS_AS_OF_DATE", DEFAULT_AS_OF.isoformat()))
    csv_dir = db_path.parent / "csv"
    print(f"Generating synthetic WMS data into {db_path} (first run, about 15 seconds)...")
    generate(csv_dir, as_of, scale)
    tmp = db_path.with_suffix(".tmp")
    counts = load(csv_dir, tmp)
    tmp.replace(db_path)
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
