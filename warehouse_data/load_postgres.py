"""Create the schema in PostgreSQL (AlloyDB, Cloud SQL or any Postgres) and bulk-load the CSVs with COPY.

Connection settings come from the same environment variables the agent uses (see warehouse_agent/db.py):
  alloydb:  ALLOYDB_INSTANCE_URI or ALLOYDB_HOST/PORT, ALLOYDB_USER, ALLOYDB_PASSWORD, ALLOYDB_DATABASE
  cloudsql: CLOUD_SQL_INSTANCE (project:region:instance) or POSTGRES_HOST/PORT, POSTGRES_USER,
            POSTGRES_PASSWORD (or DB_PASSWORD), POSTGRES_DB
  postgres: POSTGRES_HOST/PORT, POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB

    python -m warehouse_data.load_postgres --target alloydb --csv data/csv --drop --create-db
    python -m warehouse_data.load_postgres --target cloudsql --csv data/csv --drop --create-db
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from warehouse_data.schema import TABLES, ddl


def create_database(target: str) -> None:
    """Create the target database (default wms) by connecting to the built-in `postgres` database."""
    from warehouse_agent.db import PostgresBackend

    name = PostgresBackend(target).database
    if not name.replace("_", "").isalnum():
        raise ValueError(f"Unsafe database name: {name}")
    conn = PostgresBackend(target, database="postgres")._conn()
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


def load(csv_dir: Path, drop: bool, target: str = "alloydb") -> None:
    from warehouse_agent.db import PostgresBackend

    backend = PostgresBackend(target)
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
    p.add_argument("--target", choices=["alloydb", "cloudsql", "postgres"],
                   default=os.environ.get("WMS_DB_BACKEND") if os.environ.get("WMS_DB_BACKEND") in
                   ("alloydb", "cloudsql", "postgres") else "alloydb")
    p.add_argument("--csv", default="data/csv", type=Path)
    p.add_argument("--drop", action="store_true", help="Drop and recreate tables first")
    p.add_argument("--create-db", action="store_true", help="Create the database first if it does not exist")
    a = p.parse_args()
    if a.create_db:
        create_database(a.target)
    load(a.csv, a.drop, a.target)


if __name__ == "__main__":
    main()
