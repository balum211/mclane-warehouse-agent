# Google Antigravity prompts: warehouse management agent

Ready-to-paste prompts for building, extending and deploying this project in Google Antigravity.
They follow the codelabs you were given: Getting Started and Building with Antigravity (IDE install
steps skipped), Spec-Driven ADK Agent Development with Antigravity and Spec-kit, Beyond Vibe Coding,
and Getting Started with Antigravity Skills.

Placeholders look like `{{PROJECT_ID}}`. Paste one prompt at a time into the Agent Manager, review
the artifacts it produces (task list, implementation plan, walkthrough), and leave comments on the
artifact rather than re-prompting for document-wide changes.

**Working agreements for every session**
- Use **Planning** mode for anything that changes more than one file; **Fast** mode for one-liners.
- Terminal policy: "Request review" for `gcloud`, `bq`, `adk deploy`; auto-run is fine for `make test`.
- The repo already contains `AGENTS.md`, `.agents/rules/project-context.md`, six skills in
  `.agents/skills/`, a spec-kit constitution and feature specs `specs/001-warehouse-ops-copilot/`
  and `specs/002-delivery-otd-geofence/`. The agent reads these automatically, so prompts stay short.
- Layout matches the sdd-adk-antigravity codelab starter: Python 3.12 with `uv`, the agent folder
  (`warehouse_agent/`, with its own `.env`) at the repo root next to `server.py`, `uv run adk web .`
  to run it, `.agents/{rules,skills,workflows}` and `.specify/`. To drop this agent into your
  `sdd-adk-agents-agy` project instead, follow [SDD_ADK_AGENTS_AGY.md](SDD_ADK_AGENTS_AGY.md).

---

## 0. Open the workspace (no IDE install steps)

Open the cloned `mclane-warehouse-agent` folder as the Antigravity workspace, then:

```text
Set up this workspace for local development and verify it works. Steps:
1. Run `uv sync` (Python 3.12 from .python-version; the dev group with pytest is included).
2. Copy .env.example to warehouse_agent/.env. Set GOOGLE_CLOUD_PROJECT={{PROJECT_ID}},
   GOOGLE_CLOUD_LOCATION=global, GOOGLE_GENAI_USE_VERTEXAI=True and keep WMS_DB_BACKEND=sqlite.
3. Run `uv run make data` to generate the synthetic WMS and delivery dataset, then `uv run make test`.
4. Start `uv run adk web .` and, in the browser, open the warehouse_agent app and ask
   "Give me the shift briefing for MTX", then "Why is restaurant OTD down at FDL?". Capture
   screenshots in the walkthrough.
Stop and ask me if gcloud authentication is needed; don't print credentials.
```

## 1. MCP servers (ADK docs for grounding)

Antigravity reads MCP servers from `$HOME/.gemini/config/mcp_config.json` (open it from
Settings > Customizations > Installed MCP Servers > Open MCP Config). Merge in the `adk-docs-mcp`
entry from [`mcp_config.example.json`](../mcp_config.example.json), the same server the
sdd-adk-antigravity codelab uses:

```json
{
  "mcpServers": {
    "adk-docs-mcp": {
      "command": "uvx",
      "args": ["--from", "mcpdoc", "mcpdoc", "--urls", "AgentDevelopmentKit:https://adk.dev/llms.txt",
               "--transport", "stdio"]
    }
  }
}
```

Optional: the example's `wms-toolbox` entry runs MCP Toolbox over stdio with `toolbox/tools.yaml`
(AlloyDB + BigQuery) or `toolbox/tools.cloudsql.yaml` (the codelab's Cloud SQL instance) so
Antigravity itself can query the hackathon data, including OTD, yard dwell and PC*MILER lanes.
Use an absolute path to the tools file and restrict tools in Project Settings if you want.

## 2. Project context

```text
Research this repository and update .agents/rules/project-context.md so it is an accurate,
compact project context document: business context (McLane retail and restaurant distribution,
three WMS platforms), data model, agent architecture, conventions, and the planted demo scenarios.
Use the adk-docs MCP server to confirm current ADK APIs. Communicate efficiently.
```

## 3. Spec-kit setup and constitution

Spec-kit commands live in `.agents/workflows/` (slash commands) and `.specify/` (templates,
scripts, memory). This repo ships the constitution and specs but not the spec-kit command files.
Copy them from your clone of the codelab starter with
`bash scripts/install_speckit.sh ~/sdd-adk-agents-agy` (or `make speckit SRC=~/sdd-adk-agents-agy`),
or run `bash scripts/install_speckit.sh --specify-cli` to use the spec-kit CLI. Both keep the
existing `.specify/memory/constitution.md`.

Review or amend the constitution:

```text
/speckit.constitution Review the existing constitution for this small hackathon project and keep it
at most seven principles. It must keep: grounded and quantified recommendations with approver
roles; safety, temperature-zone and FEFO as hard constraints; human approval for any state change
via propose_action; one canonical model across Manhattan Active, Blue Yonder and Argent; portable
SQL through warehouse_agent/db.py (or MCP Toolbox tools.yaml if we switch); session state via ADK
ToolContext/output_key; tests (including DuckDB portability and the scripted agent flow) must pass
before merge. Bump the version only if you change a principle.
```

## 4. Spec-driven features

Each feature runs the same cycle: `/speckit.specify` -> `/speckit.clarify` (optional) ->
`/speckit.plan` -> `/speckit.tasks` -> `/speckit.analyze` (optional) -> `/speckit.implement`.
Review `spec.md` and `plan.md` artifacts before approving implementation.

### 4.1 (Reference) Rebuild the MVP from scratch

Use this if you want to show judges the whole build in Antigravity; the result should match
`specs/001-warehouse-ops-copilot/`.

```text
/speckit.specify Build a warehouse operations copilot for a US retail and restaurant distributor
(dry, chilled and frozen DCs) running Manhattan Active WM, Blue Yonder WMS and Argent.
Users are shift supervisors, DC managers, inventory control and dock leads. They need:
1) slotting recommendations by velocity, cube, affinity and ergonomics with pick-travel savings;
2) wave and task planning that sequences waves by trailer cutoff and balances labor across zones
   and shifts in real time, including the labor gap when associates call out;
3) dock scheduling that predicts arrivals, flags late carriers, trailers waiting for doors
   (detention), double bookings and cold loads on ambient doors, and recommends doors;
4) inventory integrity: negative stock, over-allocation, expired-but-available, cycle-count
   variances, FEFO/expiry risk, replenishment and prioritized counts;
5) a supervisor copilot that answers questions like "Why are we behind in Zone C?" in under 100
   words with one next action, a start-of-shift briefing, and a mid-shift disruption re-plan
   (late inbound trailer + labor shortfall).
Every recommendation shows rationale, expected gain (picks/hr, travel ft, dwell minutes, orders
protected) and who must approve. Safety, temperature zones and FEFO are hard constraints. Agents
only propose changes; humans approve. Use synthetic data for six DCs anchored to 2026-10-27 10:30
with planted problems for the demo.
```

```text
/speckit.clarify
```

```text
/speckit.plan Use Python 3.11 and Google ADK. Architecture: an orchestrator LlmAgent that routes to
specialist LlmAgents (inventory, slotting, fulfillment, labor, dock_yard, wms_integration,
data_analyst) plus two SequentialAgent pipelines whose first step is a ParallelAgent of
collectors with output_key and whose second step is a writer with an instruction provider that
reads session state (shift briefing; disruption re-plan). Tools are plain Python functions with
Google-style docstrings returning dicts with status. One canonical schema module renders DDL for
SQLite, BigQuery and AlloyDB; a db.py adapter runs portable SQL ({table} placeholders, :param binds)
on all three. Deterministic synthetic data generator and loaders. Tests: tool tests on SQLite,
DuckDB portability test, end-to-end agent flow with a scripted BaseLlm (no live Gemini).
Deployment: Vertex AI Agent Engine registered in Gemini Enterprise; Cloud Run alternative. Use the
ADK docs MCP server and the adk-wms-tool-builder and wms-portable-sql skills.
```

```text
/speckit.tasks
```

```text
/speckit.implement
```

### 4.2 (Reference) McLane delivery view: PC*MILER, geofences, dwell and OTD

Use this to show how `specs/002-delivery-otd-geofence/` was built.

```text
/speckit.specify Extend the warehouse copilot with McLane's delivery view. Transportation and DC
managers need: Retail and Restaurant on-time delivery (OTD) this week vs last, by DC, route, chain
and customer, with why stops were late (late departure, customer dwell, traffic, route plan);
dwell time changes for inbound trailers in the DC yard (gate-in to gate-out, by carrier) and for our
trucks at customers (by chain); geofence activity (trailers in the yard that have not checked in,
detention risk, trucks at customers now); PC*MILER practical miles and drive time for lanes and
routes; customer geolocation and receiving windows (restaurants 60 min, retail 120 min); and, during
a mid-shift disruption, which customer windows tomorrow's late waves will miss and how many the
re-plan recovers. Same rules: grounded numbers, approver on every action, food safety first.
```

```text
/speckit.plan Add tables geofences, geofence_events, lane_miles, route_trips and route_stops plus
lat/lon, receiving window and standard dwell on customers and distribution_centers in
warehouse_agent/schema.py. Generate them in warehouse_data/delivery.py with its own random stream so
existing demo numbers do not move, planting: FDL restaurant late departures this week, chronically
late route MTX-R07 (drive time over PC*MILER), Taco Trail dwell up at FDL, Lonestar yard dwell up at
MTX, and a trailer in the MTX yard geofence that has not checked in. Add warehouse_agent/pcmiler.py
(PC*MILER Web Services when PCMILER_API_KEY is set, else lane_miles, else an estimate), seven tools
in tools/delivery.py, a delivery_otd_agent, a delivery snapshot collector in the shift briefing and
a replan_otd_agent in the disruption re-plan. Use the wms-portable-sql, adk-wms-tool-builder and
mclane-otd-dwell skills; add tests and keep make test green.
```

### 4.3 Temperature excursion monitoring (cold chain)

```text
/speckit.specify Add cold-chain temperature excursion monitoring. Reefer trailers at doors and
cooler/freezer zones report temperature readings every 5 minutes. Detect excursions (cooler above
41F for more than 30 minutes, freezer above 0F for more than 15 minutes), identify the inventory
lots and inbound ASN lines exposed, recommend HOLD and QA inspection, and include excursions at the
top of the shift briefing. Supervisors ask "Any temperature problems right now?".
```

```text
/speckit.plan Add a temperature_readings table (dc_id, sensor_id, zone or door_id, reading_time,
temp_f) to warehouse_agent/schema.py and the generator with two planted excursions (one MTX freezer
aisle, one FDL reefer at a door). Add tools detect_temperature_excursions and get_exposed_inventory
to a new tools/cold_chain.py, give them to inventory_agent and dock_yard_agent, add the first to
inventory_snapshot_agent, and update prompts. Use the wms-portable-sql and adk-wms-tool-builder
skills. Add tests and keep make test green.
```

### 4.4 Real-time events with Pub/Sub

```text
/speckit.specify Make the copilot near-real-time. WMS task completions, ASN receipts, appointment
check-ins and inventory adjustments arrive as events. The copilot's answers must reflect events
within 2 minutes, and the supervisor gets a proactive alert when a wave is projected to miss cutoff
or a trailer waits more than 60 minutes.
```

```text
/speckit.plan Create Pub/Sub topics wms-task-events, wms-asn-events, wms-dock-events,
wms-inventory-events with a JSON schema per canonical table. Add an event simulator that replays the
synthetic data as events, and a Cloud Run subscriber that upserts into AlloyDB (operational) and
streams to BigQuery (history). Add an alerting job that calls get_wave_progress and
get_dock_exceptions every 5 minutes and posts to a Google Chat webhook. Keep tools unchanged; only
the data freshness changes. Document the infra in deploy/.
```

### 4.5 Vertex AI arrival-time prediction for the dock

```text
/speckit.specify Replace the carrier-median baseline in predict_dock_arrivals with a learned ETA model
that uses carrier, lane, day of week, hour, weather and live telematics when available, and reports
a confidence interval. Dock leads see predicted arrival, confidence and door-collision risk.
```

```text
/speckit.plan Train a BigQuery ML or Vertex AI tabular regression model on dock_appointments history
(feature view in BigQuery). Serve predictions from BigQuery ML ML.PREDICT inside the BigQuery
backend and keep the carrier-median baseline as the fallback for SQLite/AlloyDB. Evaluate with MAE
in minutes versus the baseline and record the result in research.md.
```

### 4.6 Batch picking and pick-path sequencing

```text
/speckit.specify Recommend batch picking for small orders and a serpentine pick sequence per
batch, quantifying travel saved versus discrete order picking, so supervisors can release batches
for the cooler and freezer where pickers spend the most time.
```

## 5. Beyond vibe coding: a supervisor "Shift Command Center" web page

Follows the Beyond Vibe Coding codelab flow (PRD -> design panel -> design doc -> build -> review).

**PRD (ask me questions first)**
```text
I want a one-page "Shift Command Center" web UI for DC shift supervisors that talks to this ADK
agent through `adk api_server`. Before writing anything, research what supervisors need on a
warehouse floor display and use the ask_question tool to ask me up to 5 questions. Then write a PRD
covering user experience and scope only (no technology choices) to
docs/plans/{{YYYY-MM-DD}}-shift-command-center-prd.md.
```

**Design panel with subagents**
```text
Run a panel of three subagents (UX for a noisy warehouse floor and tablets, accessibility, visual
design) and have each produce one mockup of the Shift Command Center from the PRD, rendered in the
browser. Show me all three side by side. After I pick one, update the PRD to reference it.
```

**Technical design**
```text
Write a technical design doc for the chosen mockup: file structure, how it calls the ADK
api_server (/run_sse with app warehouse_agent), state flow (Idle -> Loading -> Briefing ->
Replanning -> AwaitingApproval) as a Mermaid diagram, components, error handling, and how approvals
call decide_action through the agent. Save it next to the PRD.
```

**Build and review**
```text
Implement the Shift Command Center from the PRD, chosen mockup and design doc in ui/. Then run two
fresh review subagents: one checks the build against the PRD requirements, the other reviews code
quality and accessibility. Fix what they find and give me a walkthrough with screenshots.
```

## 6. Skills

The repo ships `wms-portable-sql`, `adk-wms-tool-builder`, `wms-synthetic-data`,
`gemini-enterprise-deploy`, `wms-demo-facts` and `mclane-otd-dwell` in `.agents/skills/`
(workspace scope; each is a folder with a `SKILL.md` that has `name` and `description` frontmatter,
plus optional `scripts/` and `references/`). Global skills go in `~/.gemini/config/skills/`.

**Use a skill**
```text
Using the wms-demo-facts skill, print the demo facts for MTX and check that docs/DEMO_SCRIPT.md
still matches them. Fix the doc if any number drifted.
```

**Create a new skill**
```text
Create a workspace skill in .agents/skills/wms-kpi-definitions/ with a SKILL.md (frontmatter name and
a specific description that triggers when someone asks how a warehouse KPI is defined or computed)
and a references/kpis.md that defines, with formulas and the table/columns used in this repo:
cases per labor hour, performance to standard, slotting efficiency, case fill rate, inventory record
accuracy, dock dwell, detention minutes, door utilization, short picks per 1,000 lines. Then make the
data_analyst_agent prompt reference these definitions.
```

**Skill with a script (schema validator pattern from the codelab)**
```text
Create a workspace skill wms-schema-guard with scripts/validate_schema.py that checks
warehouse_agent/schema.py: every table has a primary key in PRIMARY_KEYS, every operational table
has dc_id, column names are snake_case, and types are one of STRING, INT, FLOAT, DATE, DATETIME.
The SKILL.md must tell the agent to run the script whenever schema.py changes.
```

## 7. Data backends and deployment

**BigQuery**
```text
Using the wms-synthetic-data skill, load the dataset into BigQuery project {{PROJECT_ID}}, dataset
mclane_wms (location US). Then switch warehouse_agent/.env to WMS_DB_BACKEND=bigquery, run the
demo facts script against BigQuery and confirm the numbers match SQLite. Ask before running any
command that creates cloud resources.
```

**Cloud SQL for PostgreSQL (the sdd-adk-agents-agy instance)**
```text
Load the warehouse dataset into the Cloud SQL instance the sdd-adk-antigravity codelab created
(restaurant-db in {{REGION}}) with deploy/setup_cloudsql.sh, as a separate `wms` database so the
restaurant concierge tables are untouched. Ask me for DB_PASSWORD, never echo it. Then set
WMS_DB_BACKEND=cloudsql and CLOUD_SQL_INSTANCE in warehouse_agent/.env and run the demo facts script.
```

**AlloyDB**
```text
Provision AlloyDB with deploy/setup_alloydb.sh in {{REGION}} (ask me for the password, never echo
it), load the data, switch the backend to alloydb and run the demo facts script. Summarize cost
implications and how to delete the cluster afterwards.
```

**Agent Engine + Gemini Enterprise**
```text
Using the gemini-enterprise-deploy skill, deploy warehouse_agent to Vertex AI Agent Engine in
{{REGION}} with the BigQuery backend, smoke-test it with "Give me the shift briefing for MTX", then
register it in Gemini Enterprise app {{GE_APP_ID}}. Ask for approval before each gcloud/adk
deploy command and give me the agent's resource name at the end.
```

## 8. Demo rehearsal

```text
Start adk web and run the five demo beats in docs/DEMO_SCRIPT.md against the live agent. For each
beat, compare the answer with the wms-demo-facts output, note any wrong number, any answer over 100
words for supervisor questions, and any recommendation missing an approver. Propose prompt changes
in warehouse_agent/prompts.py to fix them, then re-run.
```

## 9. Prompt tuning loop

```text
Create an ADK eval set in tests/eval/ with 15 supervisor questions from docs/DEMO_SCRIPT.md and
their expected tool calls (for example "Why are we behind in the cooler?" -> transfer to
fulfillment_agent, diagnose_zone_backlog with dc_id and zone). Run `adk eval` and report tool
trajectory and response scores. Then suggest instruction changes for the lowest-scoring cases.
```

## 10. Delivery questions to rehearse

```text
Run these against the live agent and compare each answer with the wms-demo-facts output (delivery
section): "Why is restaurant OTD down at FDL?", "Which MTX route is always late and why?",
"Is dwell time going up anywhere?", "Which trucks are in the MTX yard right now?",
"How many PC*MILER miles is route FDL-R03 tomorrow?", "Where is Taco Trail #2084 and when do they
take deliveries?". Fix prompts in warehouse_agent/prompts.py if an answer mixes Retail and
Restaurant OTD, omits the miles source, or has no next action and approver.
```
