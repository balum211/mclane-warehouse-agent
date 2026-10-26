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
- SQL in tools must stay portable across SQLite, BigQuery and AlloyDB: follow the
  `wms-portable-sql` skill. Run `make test` (includes a DuckDB portability check) before finishing.
- The agent recommends; humans approve. Any state change goes through `propose_action`.
- Hard constraints in every recommendation: safety, temperature zones, FEFO.
- Keep supervisor-facing answers under 100 words with one clear next action and its approver.
- Don't call live Gemini in tests; use the scripted model in `tests/test_agent_flow.py`.

## Commands
| Task | Command |
|---|---|
| Install | `uv sync --extra dev` (or `pip install -e ".[dev]"`) |
| Synthetic data -> SQLite | `make data` |
| Tests | `make test` |
| Dev UI | `adk web .` then open http://localhost:8000 and pick `warehouse_agent` |
| BigQuery load | `make bq-load PROJECT=<id>` |
| Deploy | `make deploy-agent-engine`, then `make register-gemini-enterprise` |

## Layout
- `warehouse_agent/` ADK package (`root_agent` in `agent.py`, prompts in `prompts.py`, tools in `tools/`,
  canonical schema in `schema.py`, backend-agnostic data access in `db.py`)
- `warehouse_data/` synthetic data generator and loaders (SQLite, BigQuery, AlloyDB)
- `.agents/skills/` Antigravity skills; `.agents/rules/` always-on project rules
- `.specify/` spec-kit memory (constitution) and `specs/` feature specs
- `docs/` architecture, demo script, roadmap, Antigravity prompts, Gemini Enterprise guide
