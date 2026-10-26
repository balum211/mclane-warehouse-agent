# Tasks: Warehouse Operations Copilot (MVP)

## Phase 1: Setup
- [x] T001 Project skeleton, pyproject, Makefile, `.env.example`
- [x] T002 Canonical schema `warehouse_agent/schema.py` and DDL for SQLite/BigQuery/AlloyDB
- [x] T003 Synthetic data generator with planted scenarios; loaders for SQLite, BigQuery, AlloyDB
- [x] T004 Backend-agnostic `db.py`

## Phase 2: Tools (by user story)
- [x] T010 [US5] Inventory: positions, expiring (FEFO), replenishment, stockout risk, cycle counts, anomalies
- [x] T011 [US3] Slotting: velocity vs travel swaps, ergonomics, affinity, utilization
- [x] T012 [US2] Fulfillment: summary, wave progress, zone backlog diagnosis, shorts, wave release, order lookup
- [x] T013 [US1] Labor: productivity vs standards, labor requirement forecast, roster
- [x] T014 [US4] Dock: schedule, exceptions, arrival prediction, inbound impact, door recommendation, utilization
- [x] T015 [US6] Integration: landscape, interface health, field mapping, KPI comparison
- [x] T016 Analytics: data model, guarded read-only SQL
- [x] T017 Actions: propose/decide/list with approver roles

## Phase 3: Agents
- [x] T020 Specialist agents and prompts
- [x] T021 [US2] Shift briefing pipeline (parallel collectors + writer)
- [x] T022 [US1] Disruption re-plan pipeline (parallel assessors + writer)
- [x] T023 Orchestrator routing

## Phase 4: Quality and delivery
- [x] T030 Tool tests incl. planted scenarios
- [x] T031 DuckDB SQL portability test
- [x] T032 End-to-end agent flow test with scripted model
- [x] T033 Agent Engine deploy + Gemini Enterprise registration scripts
- [x] T034 Docs: architecture, demo script, roadmap, Antigravity prompts
- [ ] T035 Live run against Gemini in `adk web` and tune prompts (needs a GCP project)
- [ ] T036 BigQuery and AlloyDB load + smoke test in the hackathon project
