# Using this agent in Antigravity, Google Cloud projects and `sdd-adk-agents-agy`

This page records the compatibility review against the five Antigravity codelabs and explains the
three ways to run the warehouse agent: this repo on its own in Antigravity, inside your
`sdd-adk-agents-agy` project (the starter you cloned in the Spec-Driven ADK codelab), and deployed
to a Google Cloud project.

## Compatibility review (2026-10-28)

| Codelab convention | This repo |
|---|---|
| Python 3.12, `uv sync`, `uv run adk web .` from the repo root | `.python-version` = 3.12, `uv.lock` committed, dev tools in a `[dependency-groups]` dev group so plain `uv sync` installs pytest/ruff/duckdb |
| One agent folder at the root with its own `.env` (`restaurant_concierge/.env`: `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION=global`, `GOOGLE_GENAI_USE_VERTEXAI=True`) | `warehouse_agent/` with `root_agent` in `agent.py`, relative imports only, `.env` copied from `.env.example` (same three Vertex AI variables) |
| `server.py`: FastAPI via ADK `get_fast_api_app`, `uv run uvicorn server:app --host 0.0.0.0 --port 8080` | `server.py` added (same command, `make serve`) |
| MCP config in `$HOME/.gemini/config/mcp_config.json` with `adk-docs-mcp` (mcpdoc, `https://adk.dev/llms.txt`) | `mcp_config.example.json` (same entry, plus an optional MCP Toolbox server); docs now point at the right file and menu |
| Skills in `.agents/skills/<name>/SKILL.md` with `name` + `description` frontmatter, optional `scripts/`, `references/` | Six workspace skills in that format (`wms-portable-sql`, `adk-wms-tool-builder`, `wms-synthetic-data`, `gemini-enterprise-deploy`, `wms-demo-facts`, `mclane-otd-dwell`) |
| Rules in `.agents/rules/`, spec-kit commands in `.agents/workflows/speckit.*.md`, `.specify/{memory,templates,scripts}`, specs in `specs/<NNN-feature>/` | `.agents/rules/project-context.md`, constitution v1.1.0, specs 001 and 002. The spec-kit command files are not vendored: `scripts/install_speckit.sh` copies them from your starter clone |
| Database through MCP Toolbox `tools.yaml` on Cloud SQL for PostgreSQL (`scripts/setup_database.sh`, `DB_PASSWORD`) | Native tools work on SQLite, BigQuery, AlloyDB and now **Cloud SQL** (`WMS_DB_BACKEND=cloudsql`, `DB_PASSWORD` honoured); `toolbox/tools.cloudsql.yaml` targets the codelab's instance |
| Beyond Vibe Coding: `AGENTS.md`, PRDs in `docs/plans/`, subagent review | `AGENTS.md` at the root with commands and rules; prompts for PRD, design panel and review subagents in `docs/ANTIGRAVITY_PROMPTS.md` section 5 |

Also fixed during the review: a generator bug that could stamp a door assignment after the demo
clock, and the first-run experience (the SQLite demo database is generated automatically on first
use, so `uv run adk web .` works straight after `uv sync`).

Checked in a clean copy: `uv sync` (Python 3.12), `uv run pytest` (74 passed), first-run data
generation, and `uv run uvicorn server:app` listing `warehouse_agent` and serving the dev UI.

## Option A: this repo on its own in Antigravity

```bash
git clone https://github.com/balum211/mclane-warehouse-agent && cd mclane-warehouse-agent
uv sync
cp .env.example warehouse_agent/.env      # set GOOGLE_CLOUD_PROJECT
uv run adk web .                           # http://localhost:8000 -> warehouse_agent
bash scripts/install_speckit.sh ~/sdd-adk-agents-agy   # optional: spec-kit slash commands
```
Open the folder as the Antigravity workspace and use the prompts in
[ANTIGRAVITY_PROMPTS.md](ANTIGRAVITY_PROMPTS.md).

## Option B: add the warehouse agent to `sdd-adk-agents-agy`

The starter keeps one agent folder per app at its root (`restaurant_concierge/`), so the warehouse
agent drops in next to it and both show up in `uv run adk web .`.

```bash
cd ~/sdd-adk-agents-agy
WMS=~/mclane-warehouse-agent
cp -r $WMS/warehouse_agent $WMS/warehouse_data .            # agent + generator (for local SQLite)
cp -r $WMS/.agents/skills/{wms-portable-sql,adk-wms-tool-builder,wms-synthetic-data,mclane-otd-dwell,wms-demo-facts} .agents/skills/
cp $WMS/toolbox/tools.cloudsql.yaml ./tools.warehouse.yaml   # optional MCP Toolbox tools
mkdir -p specs && cp -r $WMS/specs/00{1,2}-* specs/          # keep the starter's own specs too
uv add google-cloud-bigquery python-dotenv "cloud-sql-python-connector[pg8000]" pg8000
cp $WMS/.env.example warehouse_agent/.env                    # set GOOGLE_CLOUD_PROJECT
uv run python -m warehouse_data.load_sqlite --generate       # or let it generate on first use
uv run adk web .                                             # pick warehouse_agent
```

Notes:
- Don't copy this repo's `AGENTS.md`, constitution or `project-context.md` over the starter's;
  append a "Warehouse agent" section to them instead so both apps keep their rules.
- `server.py` in the starter already serves every agent folder, so `uv run uvicorn server:app`
  exposes `warehouse_agent` too.
- To use the codelab's Cloud SQL instance instead of SQLite, load a separate `wms` database (the
  restaurant tables are untouched) and switch the backend:
  ```bash
  PROJECT=$GOOGLE_CLOUD_PROJECT DB_PASSWORD=... bash $WMS/deploy/setup_cloudsql.sh
  # warehouse_agent/.env
  WMS_DB_BACKEND=cloudsql
  CLOUD_SQL_INSTANCE=<project>:us-central1:restaurant-db
  DB_PASSWORD=...
  ```
- Running Toolbox for both apps: start a second Toolbox on another port
  (`toolbox --tools-file tools.warehouse.yaml --port 5001`) or merge the `sources` and `tools`
  sections into the starter's `tools.yaml`.

## Option C: a Google Cloud project (Agent Engine + Gemini Enterprise)

1. Data: BigQuery (`bash deploy/setup_gcp.sh` then `make bq-load PROJECT=<id>`), AlloyDB
   (`deploy/setup_alloydb.sh`) or Cloud SQL (`deploy/setup_cloudsql.sh`). SQLite does not deploy.
2. `warehouse_agent/.env`: `GOOGLE_GENAI_USE_VERTEXAI=True`, `GOOGLE_CLOUD_PROJECT`,
   `GOOGLE_CLOUD_LOCATION=global`, `WMS_DB_BACKEND=bigquery|alloydb|cloudsql` plus its variables,
   optional `PCMILER_API_KEY`.
3. `bash deploy/deploy_agent_engine.sh` (grants BigQuery, AlloyDB and Cloud SQL client roles to the
   Agent Engine service agent), then `bash deploy/register_gemini_enterprise.sh`.
   Details: [GEMINI_ENTERPRISE.md](GEMINI_ENTERPRISE.md).

## PC*MILER in production
The demo's `lane_miles` rows are synthetic (`source = PCMILER_SYNTH`). For McLane lanes, either
load a PC*MILER batch export into `lane_miles` (same columns, `source = PCMILER_BATCH`) or set
`PCMILER_API_KEY` (and `PCMILER_BASE_URL` if your Trimble Maps account uses a different host) for
live PC*MILER Web Services calls. Verify the response parsing in `warehouse_agent/pcmiler.py`
against your account's API version before relying on live calls.
