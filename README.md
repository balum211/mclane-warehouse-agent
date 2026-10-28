# McLane Warehouse Operations Copilot

Google ADK multi-agent system for **warehouse management across Manhattan Active WM, Blue Yonder
WMS and Argent**, built for the McLane Google hackathon (Oct 27-28, 2026). It covers slotting,
wave and labor planning, dock scheduling, inventory integrity and a supervisor copilot, plus
McLane's delivery view (**PC*MILER miles, dwell time changes, Retail and Restaurant on-time
delivery, geofences and geolocations**), over a synthetic, harmonized dataset for retail
(convenience grocery) and restaurant (foodservice) DCs.

```text
warehouse_ops_orchestrator
 |- inventory_agent         stock, FEFO / expiry, replenishment, stockout risk, cycle counts, anomalies
 |- slotting_agent          velocity vs travel swaps, SKU affinity, ergonomics, space
 |- fulfillment_agent       orders, waves vs cutoff, "why are we behind in zone X", shorts, wave sequencing
 |- labor_agent             performance vs engineered standards, labor gap, call-outs
 |- dock_yard_agent         exceptions, arrival prediction, inbound impact, door assignment
 |- delivery_otd_agent      Retail vs Restaurant OTD, dwell changes, geofences, PC*MILER miles
 |- wms_integration_agent   MA / BY / Argent mapping, interface health, cross-DC KPI scorecard
 |- data_analyst_agent      guarded read-only SQL
 |- shift_briefing_pipeline      parallel collectors (inventory, fulfillment, labor, dock, delivery) -> writer
 '- disruption_replan_pipeline   parallel assessors (dock, labor, waves, customer OTD risk) -> re-plan writer
```

## Quick start (local, about 2 minutes)
Same workflow as the sdd-adk-antigravity codelab (Python 3.12, `uv`):
```bash
uv sync                               # .venv with Python 3.12, dev tools included (or: pip install -e ".[dev]")
cp .env.example warehouse_agent/.env  # set GOOGLE_CLOUD_PROJECT; Gemini via Vertex AI
uv run make data                      # synthetic data -> data/wms.db (~277k rows; also generated on first use)
uv run make test                      # 74 tests, no Gemini calls
uv run adk web .                      # http://localhost:8000 -> warehouse_agent
uv run uvicorn server:app --port 8080 # or the FastAPI server (ADK API + UI)
```
Try: *"Give me the shift briefing for MTX"*, *"Why are we behind in the cooler?"*,
*"The Lonestar trailer is late and we're short pickers tonight. Re-plan MTX."*,
*"Why is restaurant OTD down at FDL?"*, *"Is dwell time going up anywhere?"*

Using it in Antigravity, inside your `sdd-adk-agents-agy` project, or in a Google Cloud project:
[docs/SDD_ADK_AGENTS_AGY.md](docs/SDD_ADK_AGENTS_AGY.md).

## What's in the box
| Path | What |
|---|---|
| `warehouse_agent/` | ADK package: `agent.py` (agent tree), `prompts.py` (all system prompts), `tools/` (44 tools), `schema.py` (canonical model, 28 tables), `db.py` (SQLite / BigQuery / AlloyDB / Cloud SQL / Postgres), `pcmiler.py` (PC*MILER client + geo helpers) |
| `warehouse_data/` | Deterministic synthetic data generator (`generate.py`, delivery side in `delivery.py`) + loaders for SQLite, BigQuery and PostgreSQL |
| `server.py` | FastAPI app via ADK `get_fast_api_app` (codelab style) |
| `sql/` | DDL for SQLite, BigQuery and PostgreSQL, rendered from `schema.py` by `scripts/render_schema_docs.py` |
| `tests/` | Tool tests (planted scenarios), DuckDB SQL portability, end-to-end ADK flow with a scripted model |
| `deploy/` | GCP setup, AlloyDB / Cloud SQL loading, Agent Engine deploy, Gemini Enterprise registration |
| `toolbox/` | Optional MCP Toolbox configs: `tools.yaml` (AlloyDB + BigQuery), `tools.cloudsql.yaml` (Cloud SQL) |
| `AGENTS.md`, `.agents/` | Antigravity instructions, project rules and 6 skills |
| `mcp_config.example.json` | Entries for Antigravity's `$HOME/.gemini/config/mcp_config.json` (ADK docs MCP, Toolbox) |
| `.specify/`, `specs/` | Spec-kit constitution and feature specs 001 (MVP) and 002 (delivery view); `scripts/install_speckit.sh` adds the slash commands |
| `docs/` | Architecture, demo script, roadmap, Antigravity prompts, codelab / sdd-adk-agents-agy guide, Gemini Enterprise guide, data model |

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

28 tables: items, locations, slotting, inventory lots with expiry, ASNs, orders and lines, waves,
pick tasks, associates, labor standards / activity / schedules, dock doors and appointments, cycle
counts, integration events, a source-field map, an agent action log, and the delivery view:
geofences, telematics geofence events, PC*MILER lane miles, route trips and route stops with
receiving windows (restaurant 60 min, retail 120 min). Planted problems drive the
demo: MTX night call-outs, a late trailer carrying freight tomorrow's orders need, a detention-risk
freezer trailer, a freezer load on a dry door, a double-booked door, expiring lots, pick faces
below min, mis-slotted fast movers, negative on-hand / cold product in an ambient slot, and a Blue
Yonder UOM_MISMATCH interface spike. On the delivery side: FDL restaurant OTD falling from 87% to 68%
on late departures, chronically late route MTX-R07, rising Taco Trail stop dwell and Lonestar yard
dwell, and a trailer inside the MTX yard geofence that has not checked in.
See [docs/DATA_MODEL.md](docs/DATA_MODEL.md).

## Backends
`WMS_DB_BACKEND=sqlite` (default, local) | `bigquery` | `alloydb` | `cloudsql` | `postgres`. Tools
write portable SQL once; `db.py` qualifies tables and binds parameters per backend. Load the cloud
backends with `make bq-load PROJECT=<id>`, `bash deploy/setup_alloydb.sh` or
`bash deploy/setup_cloudsql.sh` (works with the sdd-adk-antigravity codelab's Cloud SQL instance).

## PC*MILER
Miles come from PC*MILER Web Services when `PCMILER_API_KEY` is set, otherwise from the
`lane_miles` table (a PC*MILER batch export in production, synthetic `PCMILER_SYNTH` rows in the
demo), otherwise a labelled estimate. Every answer names its source.

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
- Codelab compatibility review and `sdd-adk-agents-agy` integration: [docs/SDD_ADK_AGENTS_AGY.md](docs/SDD_ADK_AGENTS_AGY.md)
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
