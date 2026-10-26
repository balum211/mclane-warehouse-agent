# McLane Warehouse Operations Copilot Constitution

## Core Principles

### I. Grounded, quantified recommendations
Every answer is grounded in tool results over the canonical WMS data. Recommendations state the
rationale, the expected gain (picks/hr, travel feet, labor hours, dwell minutes, orders protected,
dollars) and the role that must approve. No invented SKUs, numbers, people or doors.

### II. Hard operational constraints
Safety, temperature zones (DRY / COOLER / FREEZER) and FEFO are never traded off for speed or
cost. Priority order for conflicts: food safety, then service (routes complete and on time), then cost.

### III. Human in the loop
Agents recommend; people decide. Every state change is recorded with `propose_action` as
PROPOSED and only `decide_action` (after explicit user approval) moves it to APPROVED. Agents never
claim a change was made in a WMS.

### IV. One canonical model, three WMS platforms
Manhattan Active WM, Blue Yonder WMS and Argent are harmonized into `warehouse_agent/schema.py`.
Tools are platform-agnostic; source-specific names live only in `wms_field_map`.

### V. Portable data access
Tools write SQL once (portable subset, `{table}` placeholders, `:param` binds) and run on SQLite,
BigQuery and AlloyDB through `warehouse_agent/db.py`. Session state uses ADK `ToolContext` /
`output_key`, never globals.

### VI. Test before demo
`make test` passes before any merge: tool behaviour on planted scenarios, DuckDB SQL portability,
and an end-to-end agent flow with a scripted model (no live Gemini calls in tests).

### VII. Simple
Small, readable modules; plain-typed tool arguments; no new frameworks unless a spec justifies them.

## Operating constraints
- Supervisor-facing answers stay under 100 words with one next action unless more detail is asked for.
- Data is synthetic and fictional; vendor field and message names are illustrative.
- Secrets only via environment (`warehouse_agent/.env`), never in code or specs.

## Development workflow
Spec-driven: `/speckit.specify` -> `/speckit.clarify` (optional) -> `/speckit.plan` ->
`/speckit.tasks` -> `/speckit.analyze` (optional) -> `/speckit.implement`, one feature folder per
change in `specs/`.

## Governance
This constitution supersedes ad-hoc preferences. Amendments bump the version and are recorded here.

**Version**: 1.0.0 | **Ratified**: 2026-10-26 | **Last Amended**: 2026-10-26
