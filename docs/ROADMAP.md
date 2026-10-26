# Implementation roadmap, risks and success metrics

Sections 4 and 5 of the hackathon brief.

## 4. Roadmap: hackathon MVP vs 90-day pilot

| Area | Hackathon MVP (Oct 27-28, this repo) | 90-day pilot (1-2 DCs) |
|---|---|---|
| Data | Synthetic, harmonized schema for 6 DCs; SQLite / BigQuery / AlloyDB | Read replicas or CDC feeds from Manhattan Active (REST/events), Blue Yonder (integrator IFDs) and Argent exports into BigQuery; AlloyDB for low-latency operational reads |
| Real time | Demo clock; batch snapshot | Pub/Sub topics for task completions, ASNs, appointments, inventory adjustments; 1-5 minute freshness |
| Slotting | Velocity vs travel swaps, affinity, ergonomics | Add cube fit, seasonality, Vertex AI velocity forecast; weekly re-slot batch with move labor cost |
| Wave / labor | EDF sequencing, labor gap by zone, OT options | Live LMS standards per task type, travel-aware pick path, intraday re-forecast every 30 min |
| Dock | Rule-based exceptions, carrier-median ETA, door recommender | Vertex AI ETA model using telematics, traffic and history; yard management integration |
| Inventory integrity | Rule-based anomaly scan, FEFO, replenishment, cycle-count list | Vertex AI anomaly detection on transaction streams; risk-based cycle counting program |
| Copilot | ADK multi-agent, Gemini Enterprise, guarded SQL, photo checks | SSO roles, per-DC data scoping, evaluation set (ADK eval) with 50+ supervisor questions |
| Actions | Logged PROPOSED/APPROVED in `agent_actions` | Write-back of approved actions via WMS APIs / integration layer with audit trail |
| Ops | Local + Agent Engine | CI (tests + evals), Cloud Monitoring, cost dashboards, prompt/version management |

**Pilot plan**
- Weeks 1-3: data contracts and pipelines for one Manhattan Active DC and one Argent DC; security review.
- Weeks 4-6: shadow mode; supervisors compare copilot recommendations with what they did.
- Weeks 7-10: assisted mode; approved actions written back for dock door changes and replenishment.
- Weeks 11-13: measure against baseline; decide on scale-out to Blue Yonder DCs.

## 5. Risks, change management, success metrics

### Risks and mitigations
| Risk | Mitigation |
|---|---|
| Data quality and latency differ by WMS | Canonical schema with field map; freshness shown in every answer; flag data gaps |
| Wrong or invented numbers | Tools compute numbers; prompts forbid invention; evals check facts; human approval |
| Unsafe recommendation (temperature, safety, FEFO) | Hard constraints enforced in tool code, not only prompts; tests guard them |
| Over-automation | PROPOSED/APPROVED workflow with named approver role; no direct WMS writes in MVP |
| Vendor interface variance (MA / BY / Argent) | Integration layer owns write-back; mappings validated against vendor specs |
| Cost and latency of LLM calls | Flash model for collectors; parallel agents; cache-friendly prompts |
| Security / access | Gemini Enterprise SSO; per-DC scoping; read-only SQL guard; secrets in env / Secret Manager |

### Change management
- Co-design with two shift supervisors and one dock lead; use their questions as the eval set.
- Shadow mode first so trust is earned before actions are approved.
- Short answers with one next action fit the floor; the shift briefing replaces a manual report.
- Champions per shift; weekly review of approved vs rejected actions to tune prompts and rules.

### Success metrics (pilot targets vs baseline)
| KPI | Target |
|---|---|
| Cases per labor hour (picking) | +5-8% |
| Pick travel per case | -10-15% after re-slot |
| Waves completed before cutoff | 98%+ |
| Dock dwell (inbound) | -20%; detention charges -30% |
| Inventory record accuracy | 97%+ |
| Short picks per 1,000 lines | -25% |
| Expired / short-dated shrink $ | -20% |
| Supervisor adoption | 80% of supervisors weekly; 70%+ of proposed actions approved |
