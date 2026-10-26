"""Ad-hoc analytics: schema description and guarded read-only SQL."""

from __future__ import annotations

import re

from .. import db
from .common import error, ok
from ..schema import TABLES

MAX_ROWS = 200
_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|merge|drop|alter|create|truncate|grant|revoke|call|copy|attach|detach|pragma|"
    r"execute|exec|replace|vacuum|set|begin|commit|rollback|export|load)\b", re.I)
_TABLE_REF = re.compile(r"\b(from|join)\s+([A-Za-z_][\w.`\"]*)", re.I)


def describe_data_model(table: str = "") -> dict:
    """Describe the canonical WMS tables and columns so you can write correct SQL.

    Args:
        table: Optional table name for detail on one table. Empty lists every table with its columns.

    Returns:
        Tables, columns, types and descriptions, plus the SQL dialect of the active backend.
    """
    backend = db.get_backend()
    if table:
        if table not in TABLES:
            return error(f"Unknown table {table}. Tables: {', '.join(TABLES)}")
        return ok(dialect=backend.dialect, table=table,
                  columns=[{"name": n, "type": t, "description": d} for n, t, d in TABLES[table]])
    return ok(dialect=backend.dialect,
              tables={t: [c[0] for c in cols] for t, cols in TABLES.items()},
              conventions=["All operational tables have dc_id", "Quantities are in cases",
                           "Dates are DATE, timestamps are DATETIME/TIMESTAMP (no time zone)",
                           "Join items on sku, locations on location_id, orders on order_id"])


def validate_sql(sql: str) -> str | None:
    """Return an error message if `sql` is not a single read-only SELECT, else None."""
    body = re.sub(r"--[^\n]*|/\*.*?\*/", " ", sql, flags=re.S).strip().rstrip(";").strip()
    if ";" in body:
        return "Only a single statement is allowed."
    if not re.match(r"^(select|with)\b", body, re.I):
        return "Only SELECT (or WITH ... SELECT) queries are allowed."
    if _FORBIDDEN.search(re.sub(r"'[^']*'", "''", body)):
        return "Query contains a forbidden keyword; this tool is read-only."
    for _kw, name in _TABLE_REF.findall(body):
        clean = name.strip('`"').split(".")[-1]
        if clean.lower() not in TABLES and not name.startswith("("):
            # Could be a CTE name; allow names defined in a WITH clause.
            if not re.search(rf"\b{re.escape(clean)}\s+as\s*\(", body, re.I):
                return f"Unknown table '{clean}'. Use describe_data_model to list tables."
    return None


def run_readonly_sql(sql: str) -> dict:
    """Run an ad-hoc read-only SQL query against the WMS data (for questions no other tool answers).

    Use plain table names (e.g. FROM inventory JOIN items ...); they are qualified automatically for
    the active backend. Call describe_data_model first if unsure about columns. Results are capped
    at 200 rows.

    Args:
        sql: A single SELECT statement.

    Returns:
        Columns and rows, or an error message explaining why the query was rejected or failed.
    """
    problem = validate_sql(sql)
    if problem:
        return error(problem)
    body = re.sub(r"--[^\n]*", " ", sql).strip().rstrip(";")
    body = body.replace("{", "{{").replace("}", "}}")

    def qualify(m):
        name = m.group(2).strip('`"')
        short = name.split(".")[-1]
        return f"{m.group(1)} {{{short}}}" if short.lower() in TABLES else m.group(0)

    body = _TABLE_REF.sub(qualify, body)
    wrapped = f"SELECT * FROM ({body}) AS q LIMIT {MAX_ROWS + 1}"
    try:
        rows = db.query(wrapped)
    except Exception as e:  # surface DB errors to the model so it can fix its SQL
        return error(f"{type(e).__name__}: {str(e)[:500]}")
    return ok(row_count=min(len(rows), MAX_ROWS), truncated=len(rows) > MAX_ROWS,
              columns=list(rows[0].keys()) if rows else [], rows=rows[:MAX_ROWS])
