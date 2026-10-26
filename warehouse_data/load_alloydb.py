"""Create the schema in AlloyDB for PostgreSQL and bulk-load the CSVs with COPY.

Connection settings come from the same environment variables the agent uses:
ALLOYDB_INSTANCE_URI (via the AlloyDB Python Connector) or ALLOYDB_HOST/PORT
(for example the AlloyDB Auth Proxy on 127.0.0.1:5432), plus ALLOYDB_USER,
ALLOYDB_PASSWORD and ALLOYDB_DATABASE.

    python -m warehouse_data.load_alloydb --csv data/csv
"""

from __future__ import annotations

import argparse
from pathlib import Path

from warehouse_data.schema import TABLES, ddl


def create_database() -> None:
    """Create ALLOYDB_DATABASE (default wms) by connecting to the built-in `postgres` database."""
    import os

    from warehouse_agent.db import AlloyDBBackend

    name = os.environ.get("ALLOYDB_DATABASE", "wms")
    if not name.replace("_", "").isalnum():
        raise ValueError(f"Unsafe database name: {name}")
    conn = AlloyDBBackend(database="postgres")._conn()
    try:
        conn.autocommit = True
        cur = conn.cursor()
        cur.paramstyle = "named"
        cur.execute("SELECT 1 FROM pg_database WHERE datname = :name", {"name": name})
        if not cur.fetchall():
            cur.execute(f'CREATE DATABASE "{name}"')
            print(f"Created database {name}")
    finally:
        conn.close()


def load(csv_dir: Path, drop: bool) -> None:
    from warehouse_agent.db import AlloyDBBackend

    backend = AlloyDBBackend()
    conn = backend._conn()
    try:
        cur = conn.cursor()
        if drop:
            for table in TABLES:
                cur.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
        for stmt in ddl("postgres").split(";"):
            if stmt.strip():
                cur.execute(stmt)
        for table, cols in TABLES.items():
            names = ", ".join(c[0] for c in cols)
            cur.execute(f"TRUNCATE {table}")
            with open(csv_dir / f"{table}.csv", "rb") as f:
                cur.execute(f"COPY {table} ({names}) FROM STDIN WITH (FORMAT csv, HEADER true, NULL '')", stream=f)
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            print(f"{table:<26} {cur.fetchone()[0]:>8,} rows")
        conn.commit()
    finally:
        conn.close()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--csv", default="data/csv", type=Path)
    p.add_argument("--drop", action="store_true", help="Drop and recreate tables first")
    p.add_argument("--create-db", action="store_true", help="Create the database first if it does not exist")
    a = p.parse_args()
    if a.create_db:
        create_database()
    load(a.csv, a.drop)


if __name__ == "__main__":
    main()
