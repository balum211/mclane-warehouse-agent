"""Backend-agnostic data access for the warehouse agents.

Tools write SQL once, in a small portable subset, and this module runs it on
SQLite (local), BigQuery or AlloyDB (PostgreSQL). Conventions every query
follows so it runs unchanged on all three:

  * Table names are written as `{table}` placeholders and qualified here.
  * Parameters are written as `:name` and bound here (BigQuery gets `@name`).
  * No date math, casts or dialect functions in SQL. Compute dates in Python
    and pass them as parameters. Use `x * 1.0` for float division.
  * No ROUND() in SQL (PostgreSQL rejects ROUND(double, int)); round in Python.

Select the backend with WMS_DB_BACKEND = sqlite | bigquery | alloydb.
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
                "(python -m warehouse_data.load_sqlite) first.")

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


class AlloyDBBackend(Backend):
    """AlloyDB for PostgreSQL via pg8000.

    Connects through the AlloyDB Python Connector when ALLOYDB_INSTANCE_URI is
    set (IAM-authorized, no IP allowlisting), otherwise directly to
    ALLOYDB_HOST:ALLOYDB_PORT (for example through the AlloyDB Auth Proxy).
    """

    name = "alloydb"
    dialect = "PostgreSQL (AlloyDB)"

    def __init__(self, database: str | None = None):
        import pg8000.dbapi  # lazy import

        pg8000.dbapi.paramstyle = "named"
        self.pg = pg8000
        self.user = os.environ.get("ALLOYDB_USER", "postgres")
        self.password = os.environ.get("ALLOYDB_PASSWORD", "")
        self.database = database or os.environ.get("ALLOYDB_DATABASE", "wms")
        self.instance_uri = os.environ.get("ALLOYDB_INSTANCE_URI")
        self._connector = None

    def _conn(self):
        if self.instance_uri:
            if self._connector is None:
                from google.cloud.alloydb.connector import Connector

                self._connector = Connector()
            conn = self._connector.connect(self.instance_uri, "pg8000", user=self.user, password=self.password,
                                           db=self.database)
        else:
            conn = self.pg.dbapi.connect(user=self.user, password=self.password, database=self.database,
                                         host=os.environ.get("ALLOYDB_HOST", "127.0.0.1"),
                                         port=int(os.environ.get("ALLOYDB_PORT", "5432")))
        return conn

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
            elif kind == "alloydb":
                _backend = AlloyDBBackend()
            else:
                _backend = SQLiteBackend(default_sqlite_path())
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
