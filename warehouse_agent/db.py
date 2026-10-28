"""Backend-agnostic data access for the warehouse agents.

Tools write SQL once, in a small portable subset, and this module runs it on
SQLite (local), BigQuery, or PostgreSQL (AlloyDB, Cloud SQL or any Postgres).
Conventions every query follows so it runs unchanged on all of them:

  * Table names are written as `{table}` placeholders and qualified here.
  * Parameters are written as `:name` and bound here (BigQuery gets `@name`).
  * No date math, casts or dialect functions in SQL. Compute dates in Python
    and pass them as parameters. Use `x * 1.0` for float division.
  * No ROUND() in SQL (PostgreSQL rejects ROUND(double, int)); round in Python.

Select the backend with WMS_DB_BACKEND = sqlite | bigquery | alloydb | cloudsql | postgres.
With sqlite, a missing database is generated on first use (WMS_AUTO_GENERATE=false to turn off).
"""

from __future__ import annotations

import os
import re
import sqlite3
import threading
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from .schema import TABLES

_PARAM = re.compile(r"(?<![:\w]):([A-Za-z_]\w*)")
_lock = threading.Lock()
_backend: "Backend | None" = None

sqlite3.register_adapter(date, lambda d: d.isoformat())
sqlite3.register_adapter(datetime, lambda d: d.strftime("%Y-%m-%d %H:%M:%S"))


def _clean(v: Any) -> Any:
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(v, date):
        return v.isoformat()
    return v


class Backend:
    name = "base"
    dialect = "ANSI SQL"

    def qualify(self, table: str) -> str:
        return table

    def render(self, sql: str) -> str:
        return sql.format(**{t: self.qualify(t) for t in TABLES})

    def query(self, sql: str, params: dict | None = None) -> list[dict]:
        raise NotImplementedError

    def execute(self, sql: str, params: dict | None = None) -> None:
        raise NotImplementedError


class SQLiteBackend(Backend):
    name = "sqlite"
    dialect = "SQLite"

    def __init__(self, path: str):
        self.path = path
        if not Path(path).exists():
            raise FileNotFoundError(
                f"SQLite database {path} not found. Run `make data` "
                "(python -m warehouse_data.load_sqlite --generate) first.")

    def _conn(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def query(self, sql, params=None):
        with self._conn() as conn:
            cur = conn.execute(self.render(sql), params or {})
            return [{k: _clean(row[k]) for k in row.keys()} for row in cur.fetchall()]

    def execute(self, sql, params=None):
        with self._conn() as conn:
            conn.execute(self.render(sql), params or {})
            conn.commit()


class BigQueryBackend(Backend):
    name = "bigquery"
    dialect = "BigQuery GoogleSQL"

    def __init__(self, project: str, dataset: str, location: str | None = None):
        from google.cloud import bigquery  # lazy import

        self.bq = bigquery
        self.project, self.dataset = project, dataset
        self.client = bigquery.Client(project=project, location=location)

    def qualify(self, table):
        return f"`{self.project}.{self.dataset}.{table}`"

    def _params(self, params):
        bq = self.bq
        out = []
        for k, v in (params or {}).items():
            if isinstance(v, bool):
                t = "BOOL"
            elif isinstance(v, int):
                t = "INT64"
            elif isinstance(v, float):
                t = "FLOAT64"
            elif isinstance(v, datetime):
                t = "DATETIME"
            elif isinstance(v, date):
                t = "DATE"
            else:
                t = "STRING"
            out.append(bq.ScalarQueryParameter(k, t, v))
        return out

    def _run(self, sql, params):
        cfg = self.bq.QueryJobConfig(query_parameters=self._params(params))
        return self.client.query(_PARAM.sub(r"@\1", self.render(sql)), job_config=cfg).result()

    def query(self, sql, params=None):
        return [{k: _clean(v) for k, v in row.items()} for row in self._run(sql, params)]

    def execute(self, sql, params=None):
        self._run(sql, params)


class PostgresBackend(Backend):
    """PostgreSQL via pg8000: AlloyDB, Cloud SQL for PostgreSQL, or any Postgres host.

    kind="alloydb":  AlloyDB Python Connector when ALLOYDB_INSTANCE_URI is set (IAM-authorized, no IP
                     allowlisting), else ALLOYDB_HOST:ALLOYDB_PORT (e.g. the AlloyDB Auth Proxy).
                     ALLOYDB_USER / ALLOYDB_PASSWORD / ALLOYDB_DATABASE.
    kind="cloudsql": Cloud SQL Python Connector when CLOUD_SQL_INSTANCE (project:region:instance) is set,
                     else POSTGRES_HOST:POSTGRES_PORT (e.g. the Cloud SQL Auth Proxy). This is the database
                     the sdd-adk-antigravity codelab provisions.
    kind="postgres": POSTGRES_HOST:POSTGRES_PORT directly.
    Cloud SQL / Postgres credentials: POSTGRES_USER (default postgres), POSTGRES_PASSWORD (or DB_PASSWORD,
    as in the codelab's setup script) and POSTGRES_DB (default wms).
    """

    dialect = "PostgreSQL"

    def __init__(self, kind: str = "postgres", database: str | None = None):
        import pg8000.dbapi  # lazy import

        pg8000.dbapi.paramstyle = "named"
        self.pg = pg8000
        self.name = kind
        env = os.environ.get
        if kind == "alloydb":
            self.dialect = "PostgreSQL (AlloyDB)"
            self.user, self.password = env("ALLOYDB_USER", "postgres"), env("ALLOYDB_PASSWORD", "")
            self.database = database or env("ALLOYDB_DATABASE", "wms")
            self.instance = env("ALLOYDB_INSTANCE_URI")
            self.host, self.port = env("ALLOYDB_HOST", "127.0.0.1"), int(env("ALLOYDB_PORT", "5432"))
        else:
            self.dialect = "PostgreSQL (Cloud SQL)" if kind == "cloudsql" else "PostgreSQL"
            self.user = env("POSTGRES_USER", "postgres")
            self.password = env("POSTGRES_PASSWORD") or env("DB_PASSWORD", "")
            self.database = database or env("POSTGRES_DB", "wms")
            self.instance = env("CLOUD_SQL_INSTANCE") if kind == "cloudsql" else None
            self.host, self.port = env("POSTGRES_HOST", "127.0.0.1"), int(env("POSTGRES_PORT", "5432"))
        self._connector = None

    def _conn(self):
        if self.instance:
            if self._connector is None:
                if self.name == "alloydb":
                    from google.cloud.alloydb.connector import Connector
                else:
                    from google.cloud.sql.connector import Connector
                self._connector = Connector()
            return self._connector.connect(self.instance, "pg8000", user=self.user, password=self.password,
                                           db=self.database)
        return self.pg.dbapi.connect(user=self.user, password=self.password, database=self.database,
                                     host=self.host, port=self.port)

    def _cursor(self, conn):
        cur = conn.cursor()
        cur.paramstyle = "named"
        return cur

    def query(self, sql, params=None):
        conn = self._conn()
        try:
            cur = self._cursor(conn)
            cur.execute(self.render(sql), params or {})
            cols = [d[0] for d in cur.description]
            return [{c: _clean(v) for c, v in zip(cols, row)} for row in cur.fetchall()]
        finally:
            conn.close()

    def execute(self, sql, params=None):
        conn = self._conn()
        try:
            cur = self._cursor(conn)
            cur.execute(self.render(sql), params or {})
            conn.commit()
        finally:
            conn.close()


class AlloyDBBackend(PostgresBackend):
    """Backward-compatible name for PostgresBackend(kind="alloydb")."""

    def __init__(self, database: str | None = None):
        super().__init__("alloydb", database)


def _ensure_sqlite(path: str) -> None:
    """Generate the synthetic dataset on first use (local dev, a fresh Antigravity / codelab clone)."""
    if Path(path).exists() or os.environ.get("WMS_AUTO_GENERATE", "true").lower() in ("0", "false", "no"):
        return
    try:
        from warehouse_data.load_sqlite import build_sqlite
    except ImportError:  # agent folder copied without warehouse_data/
        return
    build_sqlite(Path(path))


def default_sqlite_path() -> str:
    return os.environ.get("WMS_SQLITE_PATH", str(Path(__file__).resolve().parent.parent / "data" / "wms.db"))


def get_backend() -> Backend:
    global _backend
    with _lock:
        if _backend is None:
            kind = os.environ.get("WMS_DB_BACKEND", "sqlite").lower()
            if kind == "bigquery":
                _backend = BigQueryBackend(os.environ["GOOGLE_CLOUD_PROJECT"],
                                           os.environ.get("WMS_BQ_DATASET", "mclane_wms"),
                                           os.environ.get("WMS_BQ_LOCATION", "US"))
            elif kind in ("alloydb", "cloudsql", "postgres"):
                _backend = PostgresBackend(kind)
            else:
                path = default_sqlite_path()
                _ensure_sqlite(path)
                _backend = SQLiteBackend(path)
        return _backend


def set_backend(backend: Backend | None) -> None:
    """Override the backend (tests, notebooks)."""
    global _backend
    with _lock:
        _backend = backend


def query(sql: str, params: dict | None = None) -> list[dict]:
    return get_backend().query(sql, params)


def execute(sql: str, params: dict | None = None) -> None:
    get_backend().execute(sql, params)
