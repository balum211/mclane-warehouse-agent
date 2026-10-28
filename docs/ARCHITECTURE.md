# Architecture and capability design

This document answers sections 1 and 2 of the hackathon brief for use case 3 (Warehouse
Management): architecture and data flow, then a capability-by-capability design with KPIs.
Sections 3 to 5 (demo, roadmap, risks) are in [DEMO_SCRIPT.md](DEMO_SCRIPT.md) and
[ROADMAP.md](ROADMAP.md).

## 1. Architecture and data flow

```mermaid
flowchart LR
  subgraph Sources["WMS / LMS sources (per DC)"]
    MA["Manhattan Active WM<br/>MTX, MGA"]
    BY["Blue Yonder WMS<br/>MCA, MNY"]
    AR["Argent<br/>FDL, FOH"]
    TMS["Telematics / TMS<br/>geofence ENTER/EXIT, ETAs"]
    PCM["PC*MILER<br/>(Trimble Maps)"]
  end
  subgraph Ingest["Ingestion and harmonization"]
    PS["Pub/Sub topics<br/>(orders, tasks, ASNs, appointments, inventory)"]
    MAP["Mapping layer<br/>wms_field_map + transforms"]
  end
  subgraph Data["Canonical WMS + delivery model (28 tables)"]
    BQ[("BigQuery<br/>mclane_wms<br/>analytics + history")]
    ADB[("AlloyDB / Cloud SQL for PostgreSQL<br/>operational, low latency")]
  end
  subgraph Agents["Google ADK multi-agent system (Agent Engine)"]
    ORCH["warehouse_ops_orchestrator"]
    INV["inventory_agent"]
    SLOT["slotting_agent"]
    FUL["fulfillment_agent"]
    LAB["labor_agent"]
    DOCK["dock_yard_agent"]
    OTD["delivery_otd_agent"]
    INT["wms_integration_agent"]
    SQL["data_analyst_agent"]
    BRIEF["shift_briefing_pipeline<br/>parallel collectors -> writer"]
    REPLAN["disruption_replan_pipeline<br/>parallel assessors -> writer"]
  end
  GE["Gemini Enterprise<br/>(supervisors, DC managers)"]
  ACT[("agent_actions<br/>PROPOSED -> APPROVED")]
  WB["Write-back via integration layer<br/>(WMS APIs / interfaces)"]

  MA & BY & AR & TMS --> PS --> MAP --> BQ & ADB
  PCM -- "lane_miles batch" --> BQ & ADB
  OTD -. "live miles (PCMILER_API_KEY)" .-> PCM
  GE <--> ORCH
  ORCH --> INV & SLOT & FUL & LAB & DOCK & OTD & INT & SQL & BRIEF & REPLAN
  INV & SLOT & FUL & LAB & DOCK & OTD & INT & SQL & BRIEF & REPLAN -- "tools (portable SQL)" --> BQ
  INV & SLOT & FUL & LAB & DOCK & OTD -. "or" .-> ADB
  INV & SLOT & FUL & LAB & DOCK & OTD -- propose_action --> ACT
  ACT -- human approval --> WB --> MA & BY & AR
```

**Hackathon MVP (what is in this repo)**
- Synthetic WMS and delivery data for six DCs is generated and loaded to SQLite (local), BigQuery,
  AlloyDB or Cloud SQL for PostgreSQL. Delivery data covers DC and customer geolocations, geofences,
  PC*MILER lane miles, route trips and stops with receiving windows, and telematics geofence events.
  The Pub/Sub ingestion and write-back boxes are the pilot design; in the MVP the generator stands in
  for ingestion and approved actions are logged in `agent_actions`.
- One canonical schema ([DATA_MODEL.md](DATA_MODEL.md)) means every tool works for every WMS.
- The agent runs in `adk web` locally, on Vertex AI Agent Engine, or on Cloud Run, and is
  registered in Gemini Enterprise for end users.

**Agent tree**

| Agent | ADK type | Purpose |
|---|---|---|
| `warehouse_ops_orchestrator` | LlmAgent | Front door; routes; approves/rejects actions on explicit user instruction |
| `inventory_agent` | LlmAgent | Positions, FEFO/expiry, replenishment, stockout risk, cycle counts, anomalies, photo damage checks |
| `slotting_agent` | LlmAgent | Velocity vs travel swaps, affinity, ergonomics, space |
| `fulfillment_agent` | LlmAgent | Orders, waves vs cutoff, zone backlog diagnosis, shorts, wave sequencing |
| `labor_agent` | LlmAgent | Performance vs engineered standards, labor gap, rosters |
| `dock_yard_agent` | LlmAgent | Exceptions, arrival prediction, inbound impact, door assignment |
| `delivery_otd_agent` | LlmAgent | Retail vs Restaurant OTD, routes on the road, dwell changes, geofence activity, PC*MILER miles, customer windows at risk |
| `wms_integration_agent` | LlmAgent | Cross-WMS landscape, interface health, field mapping, KPI scorecard |
| `data_analyst_agent` | LlmAgent | Guarded read-only SQL for anything else |
| `shift_briefing_pipeline` | SequentialAgent(ParallelAgent x5, writer) | Start-of-shift briefing (inventory, fulfillment, labor, dock, delivery) |
| `disruption_replan_pipeline` | SequentialAgent(ParallelAgent x4, writer) | Mid-shift re-plan (late inbound + labor shortfall), including which customer windows it costs |

The parallel collectors write their findings to session state (`output_key`), and the writer's
instruction provider reads that state, so the writer only sees facts gathered by tools.

**Guardrails**
- Hard constraints in tools, not just prompts: door recommendations filter refrigerated doors for
  cold loads; slotting swaps stay within a temperature zone; replenishment picks the FEFO lot;
  anomaly scan flags cold product in ambient slots and expired product still available.
- Human approval: `propose_action` records the expected gain and the approver role; only
  `decide_action` after explicit approval moves it to APPROVED.
- Read-only SQL guard: single SELECT, known tables only, forbidden keywords, 200-row cap.
- Supervisor answers under 100 words with one next action (prompt rule).

## 2. Capability-by-capability design

### 2.1 Slotting
- **Inputs**: pick tasks (14-day velocity), slot assignments, location travel distance, golden-zone
  flag, case weight, order co-occurrence.
- **Method**: within each temperature zone, rank SKUs by picks and faces by distance; slotting
  efficiency = ideal travel / current travel. Pair top-20% velocity SKUs in far faces with slow SKUs
  in near faces (swap); savings = picks difference x distance difference x 2 (round trip) at 4 ft/s.
  Affinity uses lift over orders; ergonomics flags heavy (35 lb or more) fast movers above floor level.
- **Tools**: `analyze_slotting`, `get_sku_affinity`, `get_slot_utilization`.
- **KPIs**: pick travel ft/week, slotting efficiency %, cases per labor hour, ergonomic flags closed.
- **Approver**: DC operations manager (RESLOT).

### 2.2 Wave and task planning, labor balancing
- **Inputs**: open orders and lines for tomorrow's ship date, waves with cutoff (departure minus 90
  min), pick tasks, engineered standards, schedules with call-outs/PTO, recent performance.
- **Method**: wave progress and projected finish from observed rate; earliest-deadline-first
  sequencing with cumulative minimum crew within the night-shift window; required vs available
  picker hours by zone at the DC's recent performance and 85% utilization; gap-closing options
  (day-shift overtime with cost, cross-trained loaders/forklift drivers, zone moves).
- **Tools**: `get_wave_progress`, `recommend_wave_release`, `forecast_labor_requirement`,
  `get_labor_productivity`, `get_shift_roster`, `diagnose_zone_backlog`.
- **KPIs**: cases (units) per labor hour, performance % to standard, waves completed before cutoff,
  overtime hours, on-time route departures.
- **Approver**: shift supervisor (RELEASE_WAVE, REBALANCE_LABOR); DC manager for overtime.

### 2.3 Dock scheduling
- **Inputs**: dock appointments, doors (refrigerated flag), carrier arrival history, ASN lines,
  tomorrow's open demand and available stock.
- **Method**: exceptions (late > 30 min, waiting > 60 min, detention risk > 120 min, no-show,
  double booking, temperature mismatch); baseline arrival prediction from carrier median lateness
  (Vertex AI forecasting in the pilot); inbound impact ranks open trailers by cases at risk for
  tomorrow's orders; door recommender respects direction, refrigeration and the time window.
- **Tools**: `get_dock_exceptions`, `predict_dock_arrivals`, `assess_inbound_impact`,
  `recommend_door`, `get_dock_schedule`, `get_door_utilization`.
- **KPIs**: dock dwell minutes, detention charges, door utilization %, inbound on-time %, cold-chain
  door violations (target 0).
- **Approver**: dock / yard lead (REASSIGN_DOOR).

### 2.4 Inventory integrity
- **Inputs**: inventory lots, slot min/max, allocations, cycle counts, expiry dates.
- **Method**: rule-based anomaly scan (negative on-hand, over-allocation, expired-but-available,
  over-capacity, temperature-zone violation, stale holds) ranked by severity into a cycle-count
  list; repeat-variance detection; FEFO expiry window; replenishment with FEFO lot selection and
  CRITICAL flag when allocated picks exceed the face; stockout risk vs open demand. Vertex AI anomaly
  detection on transaction streams is the pilot upgrade.
- **Tools**: `detect_inventory_anomalies`, `get_cycle_count_variances`, `get_expiring_inventory`,
  `get_replenishment_needs`, `get_stockout_risk`, `get_inventory_position`.
- **KPIs**: inventory record accuracy %, $ variance, shrink $ from expiry, short picks per 1,000 lines.
- **Approver**: inventory control lead (CYCLE_COUNT, REPLENISH).

### 2.5 Yard, dwell and on-time delivery (McLane transportation view)
- **Inputs**: DC and customer geolocations and geofences (yard 450 m, store 120 m, restaurant 90 m),
  telematics ENTER / EXIT events, route trips (planned vs actual departure) and stops (receiving
  window, planned arrival, ETA, actual arrival / departure), PC*MILER practical and shortest miles
  and drive time per lane, dock appointments.
- **Method**:
  - **OTD**: a stop is on time when the truck enters the customer geofence by the window end
    (restaurant windows 60 min, retail 120 min). Compared week over week, split Retail vs
    Restaurant and by route, chain or customer, with a late-reason attribution: LATE_DEPARTURE
    (trailer left 20+ min late), CUSTOMER_DWELL (extra minutes at earlier stops), TRAFFIC (drive
    time over PC*MILER), ROUTE_PLAN (window not reachable on the plan).
  - **Dwell time change**: inbound yard dwell (gate-in to gate-out) by carrier, split into
    gate-to-door, unload and door-to-gate; customer stop dwell by chain against its standard.
  - **Geofence activity**: trailers inside the yard geofence, with IN_YARD_NOT_CHECKED_IN (early or
    missed check-in) and DETENTION_RISK (over 120 min) flags; trucks currently at customers.
  - **Warehouse to delivery link**: `assess_route_otd_risk` projects each wave's finish with the
    crew on hand (earliest-deadline-first, night shift then day shift), turns minutes past cutoff
    into late departures for that wave's routes, and checks every planned stop against its window.
    Re-running with the re-plan crew shows the OTD recovered.
  - **PC*MILER**: live PC*MILER Web Services when `PCMILER_API_KEY` is set, else the `lane_miles`
    table (a PC*MILER batch export; synthetic in the demo), else a labelled great-circle x circuity
    estimate. Every answer names its source.
- **Tools**: `get_otd_performance`, `get_route_status`, `assess_route_otd_risk`,
  `get_dwell_time_changes`, `get_geofence_activity`, `get_route_miles`, `lookup_customer_site`.
- **KPIs**: OTD % Retail and Restaurant, on-time departures %, avg minutes late, inbound yard dwell
  and detention minutes, customer dwell vs standard, PC*MILER planned vs actual miles.
- **Approver**: transportation / routing manager (RESEQUENCE_ROUTE, NOTIFY_CUSTOMER); dock / yard
  lead for yard moves (REASSIGN_DOOR).

### 2.6 Supervisor copilot
- **Inputs**: everything above through the orchestrator.
- **Method**: routing to specialists, `diagnose_zone_backlog` for "why are we behind" questions,
  shift briefing and re-plan pipelines, `lookup_order` for customer questions, guarded SQL for
  the long tail; Gemini multimodal for photos of damaged cases or labels (inventory agent).
- **KPIs**: time to answer, answers with a next action and approver (target 100%), adoption
  (weekly active supervisors), actions approved vs rejected.

### 2.7 Cross-WMS integration view
- **Method**: interface health by platform and interface with spike detection; field mapping
  lookup; KPI scorecard by DC and platform (fill rate, performance, inbound on-time, inventory
  accuracy, integration error rate).
- **KPIs**: interface error rate, mean time to detect a failing interface.

## Deployment
- Local: `uv sync && uv run adk web .` (the SQLite demo database is generated on first use)
- FastAPI server, as in the sdd-adk-antigravity codelab: `uv run uvicorn server:app --port 8080`
- Agent Engine: `bash deploy/deploy_agent_engine.sh` (BigQuery, AlloyDB or Cloud SQL backend)
- Gemini Enterprise: `bash deploy/register_gemini_enterprise.sh` or the console (Agents > Add agent)
- Cloud Run alternative with the ADK web UI: `make deploy-cloud-run`

See [GEMINI_ENTERPRISE.md](GEMINI_ENTERPRISE.md) for the step-by-step.
