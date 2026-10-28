"""Human-in-the-loop actions. Agents propose; a person approves; approved actions are logged for
write-back to the owning WMS (Manhattan Active, Blue Yonder or Argent) by the integration layer."""

from __future__ import annotations

import json
import uuid

from .. import db
from .common import error, now, ok

ACTION_TYPES = {"REPLENISH", "RESLOT", "REASSIGN_DOOR", "RELEASE_WAVE", "REBALANCE_LABOR", "CYCLE_COUNT",
                "RESEQUENCE_ROUTE", "NOTIFY_CUSTOMER", "OTHER"}
# Who must approve each kind of change before it is written back to the WMS.
APPROVER = {
    "REPLENISH": "Inventory control lead",
    "CYCLE_COUNT": "Inventory control lead",
    "RESLOT": "DC operations manager",
    "REASSIGN_DOOR": "Dock / yard lead",
    "RELEASE_WAVE": "Shift supervisor",
    "REBALANCE_LABOR": "Shift supervisor (DC manager if overtime)",
    "RESEQUENCE_ROUTE": "Transportation / routing manager",
    "NOTIFY_CUSTOMER": "Transportation / routing manager",
    "OTHER": "DC operations manager",
}


def propose_action(action_type: str, dc_id: str, summary: str, rationale: str, expected_gain: str = "",
                   details_json: str = "{}") -> dict:
    """Record a recommended operational change as PROPOSED, for a person to approve.

    Never claim the change is done: tell the user it is proposed and ask them to approve or reject it.

    Args:
        action_type: REPLENISH, RESLOT, REASSIGN_DOOR, RELEASE_WAVE, REBALANCE_LABOR, CYCLE_COUNT,
            RESEQUENCE_ROUTE (stop order / departure), NOTIFY_CUSTOMER (late-delivery ETA) or OTHER.
        dc_id: DC code the action applies to.
        summary: One-line description, e.g. "Move SKU 100245 from MTX-D07-18-1 to MTX-D01-02-2".
        rationale: Why, with the numbers that justify it.
        expected_gain: Quantified benefit, e.g. "2.3 labor hrs/week", "protects 14 orders on route R03",
            "avoids 95 min detention".
        details_json: Optional JSON object with structured parameters (locations, SKUs, doors, quantities).

    Returns:
        The new action_id, its PROPOSED status and the role that must approve it.
    """
    action_type = action_type.upper()
    if action_type not in ACTION_TYPES:
        return error(f"action_type must be one of {sorted(ACTION_TYPES)}")
    try:
        details = json.loads(details_json or "{}")
    except json.JSONDecodeError:
        details = {"raw": details_json}
    details["summary"] = summary
    details["expected_gain"] = expected_gain
    details["approver_role"] = APPROVER[action_type]
    action_id = f"ACT-{uuid.uuid4().hex[:8].upper()}"
    db.execute("""
        INSERT INTO {agent_actions} (action_id, created_at, dc_id, action_type, details, rationale, status)
        VALUES (:action_id, :created_at, :dc_id, :action_type, :details, :rationale, 'PROPOSED')""",
               {"action_id": action_id, "created_at": now(), "dc_id": dc_id.upper(), "action_type": action_type,
                "details": json.dumps(details), "rationale": rationale})
    return ok(action_id=action_id, action_status="PROPOSED", summary=summary, expected_gain=expected_gain,
              approver_role=APPROVER[action_type],
              next_step=f"Ask the {APPROVER[action_type]} to approve or reject this action.")


def decide_action(action_id: str, approve: bool) -> dict:
    """Approve or reject a PROPOSED action. Call only after the user explicitly says so.

    Args:
        action_id: The id returned by propose_action.
        approve: True to approve, False to reject.

    Returns:
        The updated status. Approved actions are queued for WMS write-back by the integration layer.
    """
    rows = db.query("SELECT action_id, status FROM {agent_actions} WHERE action_id = :id", {"id": action_id})
    if not rows:
        return error(f"Action {action_id} not found.")
    if rows[0]["status"] != "PROPOSED":
        return error(f"Action {action_id} is already {rows[0]['status']}.")
    status = "APPROVED" if approve else "REJECTED"
    db.execute("UPDATE {agent_actions} SET status = :status, decided_at = :t WHERE action_id = :id",
               {"status": status, "t": now(), "id": action_id})
    return ok(action_id=action_id, action_status=status,
              note="Queued for write-back to the owning WMS." if approve else "Rejected; no change will be made.")


def list_actions(status: str = "", dc_id: str = "") -> dict:
    """List agent-proposed actions and their status.

    Args:
        status: Optional PROPOSED, APPROVED or REJECTED.
        dc_id: Optional DC code.

    Returns:
        Up to 50 most recent actions.
    """
    p: dict = {}
    where = " WHERE 1 = 1"
    if status:
        p["status"] = status.upper()
        where += " AND status = :status"
    if dc_id:
        p["dc_id"] = dc_id.upper()
        where += " AND dc_id = :dc_id"
    rows = db.query("SELECT action_id, created_at, dc_id, action_type, details, rationale, status, decided_at "
                    "FROM {agent_actions}" + where + " ORDER BY created_at DESC LIMIT 50", p)
    return ok(actions=rows)
