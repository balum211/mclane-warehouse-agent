# Implementation Plan: Warehouse Operations Copilot (MVP)

**Branch**: `001-warehouse-ops-copilot` | **Spec**: [spec.md](spec.md)

## Summary
A Google ADK multi-agent system: an orchestrator routes to seven domain specialists with Python
function tools, plus two workflow pipelines (SequentialAgent -> ParallelAgent collectors -> writer)
for the shift briefing and the disruption re-plan. Tools query one canonical WMS schema on SQLite,
BigQuery or AlloyDB.

## Technical Context
- **Language**: Python 3.11+
- **Framework**: Google ADK (`google-adk`), Gemini on Vertex AI (`WMS_AGENT_MODEL`, default gemini-3.5-flash)
- **Storage**: SQLite (dev/tests), BigQuery (`mclane_wms` dataset), AlloyDB for PostgreSQL (`wms` db)
- **Testing**: pytest; DuckDB for SQL portability; scripted `BaseLlm` for agent flow
- **Target**: Vertex AI Agent Engine, registered in Gemini Enterprise; Cloud Run alternative
- **Constraints**: no live LLM in tests; recommendations only (human approval)

## Constitution Check
| Principle | How the plan complies |
|---|---|
| I Grounded, quantified | Tools return the numbers; prompts require gain + approver |
| II Hard constraints | Door recommender filters temp-capable doors; slotting swaps stay in zone; FEFO lot selection |
| III Human in the loop | `propose_action` / `decide_action` with `agent_actions` table |
| IV Canonical model | `schema.py` + `wms_field_map` |
| V Portable data | `db.py` adapters; portability test |
| VI Test before demo | 54 tests, `make test` |
| VII Simple | One module per domain, no extra frameworks |

## Project Structure
```
warehouse_agent/      agent.py, prompts.py, config.py, db.py, schema.py, tools/<domain>.py
warehouse_data/       generate.py, load_sqlite.py, load_bigquery.py, load_postgres.py (+ load_alloydb.py alias)
tests/                test_data.py, test_tools.py, test_portability.py, test_agent_flow.py
deploy/               setup_gcp.sh, setup_alloydb.sh, deploy_agent_engine.sh, register_gemini_enterprise.sh
toolbox/tools.yaml    optional MCP Toolbox configuration
```

## Agent design
| Agent | Type | Tools |
|---|---|---|
| warehouse_ops_orchestrator | LlmAgent | get_wms_landscape, list_actions, decide_action |
| inventory_agent | LlmAgent | positions, expiring, replenishment, stockout risk, cycle counts, anomalies |
| slotting_agent | LlmAgent | analyze_slotting (incl. ergonomics), get_sku_affinity, get_slot_utilization |
| fulfillment_agent | LlmAgent | fulfillment summary, wave progress, diagnose_zone_backlog, short picks, wave release, lookup_order |
| labor_agent | LlmAgent | productivity, forecast_labor_requirement, shift roster |
| dock_yard_agent | LlmAgent | schedule, exceptions, predict arrivals, inbound impact, recommend door, utilization |
| wms_integration_agent | LlmAgent | landscape, integration health, field mapping, KPI comparison |
| data_analyst_agent | LlmAgent | describe_data_model, run_readonly_sql |
| shift_briefing_pipeline | Sequential(Parallel x4 -> writer) | snapshot subsets |
| disruption_replan_pipeline | Sequential(Parallel x3 -> writer) | dock/inbound, labor, waves |

All specialists also get `propose_action`.

## Complexity Tracking
ADK 2.x marks SequentialAgent/ParallelAgent deprecated in favour of Workflow, but Workflow cannot
yet be an LlmAgent sub-agent; keep the classic workflow agents until it can.
