"""Shared helpers for tool functions: demo clock, filters, result envelopes."""

from __future__ import annotations

import os
from datetime import date, datetime, time, timedelta

# Walking / pallet-jack travel speed used to turn feet into labor hours.
TRAVEL_FT_PER_SEC = 4.0
# Share of a scheduled shift that is direct, productive time (breaks, meetings, startup).
UTILIZATION = 0.85
SHIFT_WINDOWS = {"DAY": (time(6, 0), time(14, 30)), "NIGHT": (time(18, 0), time(2, 30))}


def as_of() -> date:
    """Business 'today'. Pinned to the synthetic data anchor unless WMS_AS_OF_DATE is set."""
    return date.fromisoformat(os.environ.get("WMS_AS_OF_DATE", "2026-10-27"))


def now() -> datetime:
    """Demo clock. Set WMS_CLOCK=real to use the wall clock against live data."""
    clock = os.environ.get("WMS_CLOCK", "10:30")
    if clock == "real":
        return datetime.now().replace(microsecond=0)
    return datetime.combine(as_of(), time.fromisoformat(clock))


def parse_date(v: str | date | None, default: date | None = None) -> date | None:
    if v in (None, ""):
        return default
    if isinstance(v, date):
        return v
    v = v.strip().lower()
    if v == "today":
        return as_of()
    if v == "tomorrow":
        return as_of() + timedelta(days=1)
    if v == "yesterday":
        return as_of() - timedelta(days=1)
    return date.fromisoformat(v[:10])


def parse_dt(v) -> datetime | None:
    if v in (None, ""):
        return None
    if isinstance(v, datetime):
        return v
    return datetime.fromisoformat(str(v).replace("T", " ")[:19])


def dc_clause(dc_id: str, alias: str = "", params: dict | None = None) -> str:
    """Return ' AND <alias>.dc_id = :dc_id' and set the param when dc_id is given."""
    if not dc_id:
        return ""
    if params is not None:
        params["dc_id"] = dc_id.strip().upper()
    col = f"{alias}.dc_id" if alias else "dc_id"
    return f" AND {col} = :dc_id"


def in_clause(name: str, values: list, params: dict) -> str:
    """Build ':name0, :name1, ...' for an IN list and add the params."""
    keys = []
    for i, v in enumerate(values):
        params[f"{name}{i}"] = v
        keys.append(f":{name}{i}")
    return ", ".join(keys) or "NULL"


def ok(**data) -> dict:
    return {"status": "success", "as_of": now().strftime("%Y-%m-%d %H:%M"), **data}


def error(message: str) -> dict:
    return {"status": "error", "error_message": message}


def r1(x) -> float:
    return round(float(x or 0), 1)


def pct(n, d) -> float | None:
    return round(100.0 * float(n) / float(d), 1) if d else None
