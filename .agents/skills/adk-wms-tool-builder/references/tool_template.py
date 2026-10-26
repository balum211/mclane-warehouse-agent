"""Template for a new warehouse tool. Copy into warehouse_agent/tools/<domain>.py."""

from datetime import timedelta

from .. import db
from .common import as_of, dc_clause, error, ok, r1


def get_example_metric(dc_id: str, days: int = 7) -> dict:
    """One-line summary the model reads to decide when to call this tool.

    Explain the business meaning and any thresholds the agent should apply.

    Args:
        dc_id: DC code (MTX, MGA, MCA, MNY, FDL, FOH).
        days: Look-back window in days (default 7).

    Returns:
        What the dict contains, including the numbers that quantify impact.
    """
    if not dc_id:
        return error("dc_id is required.")
    p = {"d0": as_of() - timedelta(days=int(days))}
    rows = db.query(f"""
        SELECT c.sku, SUM(c.variance_value) AS variance_usd
        FROM {{cycle_counts}} c
        WHERE c.count_date >= :d0{dc_clause(dc_id, 'c', p)}
        GROUP BY c.sku""", p)
    total = sum(r["variance_usd"] for r in rows)
    return ok(dc_id=dc_id.upper(), rows=rows[:20], total_usd=r1(total))
