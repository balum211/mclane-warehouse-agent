# McLane Warehouse Operations Copilot

Google ADK multi-agent system for **warehouse management across Manhattan Active WM, Blue Yonder
WMS and Argent**, built for the McLane Google hackathon (Oct 27-28, 2026). It covers slotting,
wave and labor planning, dock scheduling, inventory integrity and a supervisor copilot over a
synthetic, harmonized WMS dataset for retail (convenience grocery) and restaurant (foodservice) DCs.

```text
warehouse_ops_orchestrator
 |- inventory_agent         stock, FEFO / expiry, replenishment, stockout risk, cycle counts, anomalies
 |- slotting_agent          velocity vs travel swaps, SKU affinity, ergonomics, space
 |- fulfillment_agent       orders, waves vs cutoff, "why are we behind in zone X", shorts, wave sequencing
 |- labor_agent             performance vs engineered standards, labor gap, call-outs
 |- dock_yard_agent         exceptions, arrival prediction, inbound impact, door assignment
 |- wms_integration_agent   MA / BY / Argent mapping, interface health, cross-DC KPI scorecard
 |- data_analyst_agent      guarded read-only SQL
 |- shift_briefing_pipeline      parallel collectors -> briefing writer
 '- disruption_replan_pipeline   parallel assessors (dock, labor, waves) -> re-plan writer
```

## Quick start (local, about 2 minutes)
```bash
uv sync --extra dev            # or: pip install -e ".[dev]"
cp .env.example warehouse_agent/.env   # set GOOGLE_CLOUD_PROJECT; Gemini via Vertex AI
make data                      # synthetic data -> data/wms.db (~240k rows)
make test                      # 54 tests, no Gemini calls
adk web .                      # http://localhost:8000 -> warehouse_agent
```
Try: *"Give me the shift briefing for MTX"*, *"Why are we behind in the cooler?"*,
*"The Lonestar trailer is late and we're short pickers tonight. Re-plan MTX."*

## What's in the box
| Path | What |
|---|---|
| `warehouse_agent/` | ADK package: `agent.py` (agent tree), `prompts.py` (all system prompts), `tools/` (37 tools), `schema.py` (canonical model), `db.py` (SQLite / BigQuery / AlloyDB) |
| `warehouse_data/` | Deterministic synthetic data generator + loaders for SQLite, BigQuery, AlloyDB |
| `sql/` | DDL for SQLite, BigQuery and AlloyDB, rendered from `schema.py` |
| `tests/` | Tool tests (planted scenarios), DuckDB SQL portability, end-to-end ADK flow with a scripted model |
| `deploy/` | GCP setup, AlloyDB provisioning, Agent Engine deploy, Gemini Enterprise registration |
| `toolbox/tools.yaml` | Optional MCP Toolbox config (AlloyDB + BigQuery tools) |
| `AGENTS.md`, `.agents/` | Antigravity instructions, project rules and 5 skills |
| `.specify/`, `specs/` | Spec-kit constitution and the feature spec / plan / tasks for this MVP |
| `docs/` | Architecture, demo script, roadmap, Antigravity prompts, Gemini Enterprise guide, data model |

## Synthetic data
Six fictional DCs anchored to **2026-10-27 10:30**:

| DC | Segment | WMS |
|---|---|---|
| MTX Central Texas Grocery (Temple, TX) | Retail | Manhattan Active WM |
| MGA Southeast Grocery (Forest Park, GA) | Retail | Manhattan Active WM |
| MCA Inland Empire Grocery (Ontario, CA) | Retail | Blue Yonder WMS |
| MNY Northeast Grocery (Baldwinsville, NY) | Retail | Blue Yonder WMS |
| FDL North Texas Foodservice (Carrollton, TX) | Restaurant | Argent |
| FOH Ohio Valley Foodservice (Columbus, OH) | Restaurant | Argent |

23 tables: items, locations, slotting, inventory lots with expiry, ASNs, orders and lines, waves,
pick tasks, associates, labor standards / activity / schedules, dock doors and appointments, cycle
counts, integration events, a source-field map and an agent action log. Planted problems drive the
demo: MTX night call-outs, a late trailer carrying freight tomorrow's orders need, a detention-risk
freezer trailer, a freezer load on a dry door, a double-booked door, expiring lots, pick faces
below min, mis-slotted fast movers, negative on-hand / cold product in an ambient slot, and a Blue
Yonder UOM_MISMATCH interface spike. See [docs/DATA_MODEL.md](docs/DATA_MODEL.md).

## Backends
`WMS_DB_BACKEND=sqlite` (default, local) | `bigquery` | `alloydb`. Tools write portable SQL once;
`db.py` qualifies tables and binds parameters per backend. Load the cloud backends with
`make bq-load PROJECT=<id>` or `bash deploy/setup_alloydb.sh`.

## Deploy
```bash
bash deploy/setup_gcp.sh                 # APIs + BigQuery
bash deploy/deploy_agent_engine.sh       # Vertex AI Agent Engine (WMS_DB_BACKEND=bigquery)
bash deploy/register_gemini_enterprise.sh  # Gemini Enterprise app
```
Details: [docs/GEMINI_ENTERPRISE.md](docs/GEMINI_ENTERPRISE.md).

## Hackathon deliverables (your section 3 output format)
1. Architecture and data flow, 2. capability design with KPIs: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
3. Mid-shift disruption demo: [docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md)
4. MVP vs 90-day pilot, 5. risks and success metrics: [docs/ROADMAP.md](docs/ROADMAP.md)
- Antigravity prompts (spec-kit, skills, beyond vibe coding, deploy): [docs/ANTIGRAVITY_PROMPTS.md](docs/ANTIGRAVITY_PROMPTS.md)
- Your hackathon prompt with placeholders filled: [docs/HACKATHON_PROMPT_FILLED.md](docs/HACKATHON_PROMPT_FILLED.md)

## Guardrails
- Agents only **propose** changes (`propose_action` records expected gain and approver role);
  `decide_action` runs only on explicit approval.
- Safety, temperature zones and FEFO are enforced in tool logic (door matching, same-zone swaps,
  FEFO lot selection, anomaly checks), not only in prompts.
- Ad-hoc SQL is read-only, single-statement, known tables, 200-row cap.

## Notes
- Default model `gemini-3.5-flash` (`WMS_AGENT_MODEL`); any Gemini model on Vertex AI works.
- ADK 2.x marks SequentialAgent / ParallelAgent deprecated in favour of Workflow, which can't yet
  be an LlmAgent sub-agent; the classic workflow agents are used until it can.
- All company, customer, carrier and associate names are fictional; WMS message and field names are
  illustrative and must be validated against vendor specifications.
