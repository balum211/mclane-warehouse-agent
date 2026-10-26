# Feature Specification: Warehouse Operations Copilot (MVP)

**Feature Branch**: `001-warehouse-ops-copilot`
**Created**: 2026-10-26
**Status**: Implemented (hackathon MVP)
**Input**: McLane hackathon use case 3, Warehouse Management across Manhattan Active, Blue Yonder
and Argent: an AI-driven warehouse assistant for slotting, wave/task planning, dock scheduling,
inventory integrity and a supervisor copilot, for dry, chilled and frozen DCs.

## User Scenarios & Testing

### User Story 1: Mid-shift disruption re-plan (Priority: P1)
A shift supervisor at MTX learns an inbound trailer is late and several night pickers called out.
They ask the copilot to re-plan tonight and get a plan that protects the earliest routes.

**Why this priority**: It is the demo's headline and the costliest daily failure mode (late routes,
shorts, overtime).

**Independent Test**: "Inbound trailer is late and we're short pickers at MTX, re-plan tonight."

**Acceptance Scenarios**:
1. **Given** a checked-in trailer carrying SKUs that tomorrow's orders need, **When** the
   supervisor asks for a re-plan, **Then** the plan doors that trailer first, names the critical SKUs
   and cases at risk, and names the approving role.
2. **Given** night call-outs, **When** the plan is produced, **Then** it shows required vs available
   picker hours by zone and the cheapest named options to close the gap, with overtime cost.
3. **Given** the re-plan, **Then** it includes a before/after table for labor gap, cases at risk and
   waves at risk.

### User Story 2: Supervisor copilot (Priority: P1)
"Why are we behind in the cooler?", "Where is Burger Barn #4312's order?", "What do I need to
worry about tonight?" answered in under 100 words with one next action.

**Acceptance Scenarios**:
1. **Given** a zone question, **Then** the copilot ranks causes (rate, blocked pick faces, shorts,
   cross-zone pickers) with evidence.
2. **Given** "shift briefing", **Then** inventory, fulfillment, labor and dock facts are gathered in
   parallel and summarized with top 3 priorities.

### User Story 3: Slotting optimization (Priority: P2)
The DC manager asks where travel is wasted. The copilot reports slotting efficiency by zone, swap
recommendations with weekly travel/labor savings, SKU affinity pairs and ergonomic flags.

### User Story 4: Dock scheduling (Priority: P2)
The dock lead sees late carriers, trailers waiting (detention risk), double-booked doors and cold
loads on ambient doors, predicted arrivals for pending trailers, and a recommended door.

### User Story 5: Inventory integrity (Priority: P2)
Inventory control gets anomalies (negative on-hand, over-allocation, expired-but-available,
over-capacity, cold product in ambient slots), expiring lots (FEFO), replenishments and a
prioritized cycle-count list.

### User Story 6: Cross-WMS view (Priority: P3)
Leadership compares KPIs across DCs and WMS platforms, sees interface error spikes, and translates
source field names.

### Edge Cases
- No DC given for a DC-specific question: ask, or offer all DCs.
- A tool returns `status: error`: explain and ask for the missing input; never fabricate.
- Ad-hoc SQL attempts writes: rejected by the guard.
- Photo upload of a damaged case: describe, state confidence, propose a HOLD.

## Requirements

### Functional Requirements
- **FR-001**: Route requests to inventory, slotting, fulfillment, labor, dock, integration or
  analyst specialists, or to the briefing / re-plan pipelines.
- **FR-002**: Every recommendation includes rationale, expected gain and approver role.
- **FR-003**: Changes are only PROPOSED until a user explicitly approves (`decide_action`).
- **FR-004**: Temperature-zone, safety and FEFO rules are enforced as hard constraints in all
  recommendations (door assignment, slotting moves, picking order).
- **FR-005**: The same tools work for Manhattan Active, Blue Yonder and Argent DCs via the
  canonical schema.
- **FR-006**: Data backends: SQLite (local), BigQuery and AlloyDB with no tool code changes.
- **FR-007**: Read-only ad-hoc SQL with a guard (single SELECT, known tables, 200-row cap).
- **FR-008**: Deployable to Vertex AI Agent Engine and registrable in Gemini Enterprise.

### Key Entities
Distribution center, item, location, slot assignment, inventory lot, ASN and ASN line, order and
order line, wave, pick task, associate, labor standard/activity/schedule, dock door, dock
appointment, cycle count, integration event, field map, agent action. See `data-model.md`.

## Success Criteria
- **SC-001**: The re-plan identifies the planted late trailer, its 3 critical SKUs and the MTX
  labor gap (verified by `tests/test_tools.py`).
- **SC-002**: Supervisor answers under 100 words with one next action.
- **SC-003**: All tools pass on SQLite and the DuckDB portability check.
- **SC-004**: The end-to-end agent flow test reaches the writer with all collector state keys set.
