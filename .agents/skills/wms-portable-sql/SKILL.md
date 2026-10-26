---
name: wms-portable-sql
description: Use when writing or changing SQL inside warehouse_agent tools, or when a tool query fails on BigQuery or AlloyDB. Enforces the portable SQL subset that runs unchanged on SQLite, BigQuery and AlloyDB (PostgreSQL), and verifies it with the DuckDB portability test.
---

# Portable SQL for the WMS tools

## Goal
Every query in `warehouse_agent/tools/*.py` must run unchanged on SQLite (local), BigQuery and
AlloyDB. `warehouse_agent/db.py` qualifies table names and converts parameters; you keep the SQL
inside the common subset.

## Rules
1. Write tables as `{table}` placeholders inside f-strings use `{{table}}`. Never hard-code
   `project.dataset.` prefixes.
2. Bind values as `:name`. Pass a dict. Every key in the dict must appear in the SQL (DuckDB and
   BigQuery reject unused or missing parameters), so build a fresh dict per query.
3. No date math or date functions (`DATE_SUB`, `INTERVAL`, `julianday`, `NOW()`). Compute dates
   in Python with `as_of()` / `now()` from `tools/common.py` and pass `date` / `datetime` objects.
4. No casts (`::date`, `CAST(x AS FLOAT64)`). For float division write `x * 1.0 / y`.
5. No `ROUND()` in SQL (PostgreSQL rejects `ROUND(double precision, int)`). Round in Python.
6. Booleans are stored as INT 0/1. Compare with `= 1`.
7. Use `COALESCE`, `CASE`, `COUNT(DISTINCT ...)`, `LIKE` with `LOWER()`; avoid `ILIKE`, `IFNULL`,
   `QUALIFY`, `FILTER (WHERE ...)`.
8. Optional filters: use `dc_clause(dc_id, alias, params)` and `in_clause(name, values, params)`.
9. Results come back with dates as ISO strings on every backend (see `db._clean`); parse with
   `parse_date` / `parse_dt` before arithmetic.

## Verify
Run `bash .agents/skills/wms-portable-sql/scripts/check_portability.sh`. It runs every tool on
DuckDB loaded with the PostgreSQL DDL (strict typing, strict parameters). Fix any failure before
finishing.

## Example
```python
p = {"ship_date": parse_date(ship_date)}
rows = db.query(f"""
    SELECT l.sku, SUM(l.qty_ordered - l.qty_picked) AS open_cases
    FROM {{order_lines}} l JOIN {{outbound_orders}} o ON o.order_id = l.order_id
    WHERE o.ship_date = :ship_date{dc_clause(dc_id, 'o', p)}
    GROUP BY l.sku""", p)
```
