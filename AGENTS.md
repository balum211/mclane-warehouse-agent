# AGENTS.md: instructions for coding agents (Google Antigravity, Gemini CLI, Claude Code)

This repo is the McLane hackathon **Warehouse Management** use case: a Google ADK (Python)
multi-agent copilot over synthetic, harmonized WMS data from Manhattan Active WM, Blue Yonder WMS
and Argent. Read `.agents/rules/project-context.md` before changing code.

## Ground rules
- Use the `ask_question` tool (or ask in chat) when a requirement is ambiguous; don't guess business rules.
- Spec first: new capabilities go through spec-kit (`/speckit.specify` -> `/speckit.plan` ->
  `/speckit.tasks` -> `/speckit.implement`). Specs live in `specs/<NNN-feature>/`.
- Save plans and PRDs to `docs/plans/{{YYYY-MM-DD}}-{{description}}.md`.
- Every tool function returns a dict with `status` (`success` | `error`) and never raises for bad input.
- SQL in tools must stay portable across SQLite, BigQuery and PostgreSQL (AlloyDB, Cloud SQL): follow the
  `wms-portable-sql` skill. Run `make test` (includes a DuckDB portability check) before finishing.
- The agent recommends; humans approve. Any state change goes through `propose_action`.
- Hard constraints in every recommendation: safety, temperature zones, FEFO.
- Keep supervisor-facing answers under 100 words with one clear next action and its approver.
- Delivery metrics (OTD Retail vs Restaurant, dwell, geofences, PC*MILER) follow the definitions in
  the `mclane-otd-dwell` skill; don't redefine them in prompts or tools.
- Don't call live Gemini in tests; use the scripted model in `tests/test_agent_flow.py`.

## Commands
| Task | Command |
|---|---|
| Install | `uv sync` (Python 3.12, dev group included; or `pip install -e ".[dev]"`) |
| Synthetic data -> SQLite | `uv run make data` (also generated on first use) |
| Tests / lint | `uv run make test`, `uv run make lint` |
| Dev UI | `uv run adk web .` then open http://localhost:8000 and pick `warehouse_agent` |
| API server (codelab style) | `uv run uvicorn server:app --host 0.0.0.0 --port 8080` |
| Spec-kit commands | `bash scripts/install_speckit.sh <path-to-sdd-adk-agents-agy>` |
| Schema docs | `python scripts/render_schema_docs.py` after changing `schema.py` |
| BigQuery load | `make bq-load PROJECT=<id>` |
| Cloud SQL / AlloyDB load | `bash deploy/setup_cloudsql.sh` / `bash deploy/setup_alloydb.sh` |
| Deploy | `make deploy-agent-engine`, then `make register-gemini-enterprise` |

## Layout
- `warehouse_agent/` ADK package (`root_agent` in `agent.py`, prompts in `prompts.py`, tools in `tools/`,
  canonical schema in `schema.py`, backend-agnostic data access in `db.py`)
- `warehouse_data/` synthetic data generator (`generate.py`, delivery side in `delivery.py`) and loaders
  (SQLite, BigQuery, PostgreSQL: AlloyDB / Cloud SQL)
- `toolbox/` MCP Toolbox configs (`tools.yaml` AlloyDB + BigQuery, `tools.cloudsql.yaml` Cloud SQL)
- `server.py` FastAPI app (ADK `get_fast_api_app`); `mcp_config.example.json` for `$HOME/.gemini/config/mcp_config.json`
- `.agents/skills/` Antigravity skills; `.agents/rules/` always-on project rules
- `.specify/` spec-kit memory (constitution) and `specs/` feature specs
- `docs/` architecture, demo script, roadmap, Antigravity prompts, Gemini Enterprise guide
