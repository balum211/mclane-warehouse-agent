# Demo script (5 minutes): mid-shift disruption at the Central Texas Grocery DC

Section 3 of the brief: a mid-shift disruption (late inbound + labor shortfall) with an AI re-plan.
All numbers below come from the synthetic dataset (seed 27, clock 2026-10-27 10:30) and are
printed by `python .agents/skills/wms-demo-facts/scripts/demo_facts.py MTX`. Gemini words its
answers differently each run, but the facts must match these.

## Setup (before the demo)
```bash
uv sync              # Python 3.12 + dependencies
uv run make data     # synthetic data -> data/wms.db (also generated on first use)
uv run adk web .     # http://localhost:8000, pick warehouse_agent
```
Or open the agent in Gemini Enterprise after `deploy/deploy_agent_engine.sh` and
`deploy/register_gemini_enterprise.sh` (BigQuery backend).

## The story
MTX (Temple, TX, Manhattan Active WM) is picking tomorrow's convenience-store routes. It is 10:30.
Six night associates called out (flu), a dry trailer from Lonestar Logistics arrived 95 minutes
late and has been waiting 115 minutes for a door, and a Coldline Reefer freezer trailer has been
waiting 175 minutes (detention).

## Beat 1 (45 s): start-of-shift briefing
> **Give me the shift briefing for MTX.**

Expected facts (parallel collectors -> briefing writer):
- Labor SHORT: 33.0 picker-hours needed for tomorrow's ship date vs 27.2 available (gap 5.8 h);
  cooler has 0 scheduled picker-hours tonight.
- Dock: 2 trailers waiting for a door (one 175 min, detention risk), 1 freezer load assigned to a
  dry door (MTX-IB01), 1 double-booked door (MTX-IB08 at 11:15).
- Inventory: CRITICAL replenishments, 3 expiring lots in 2 days, stockout risk on SKUs that are on
  the late trailer.
- Delivery: MTX retail OTD 90.9% this week (91.5% prior); route MTX-R07 at 55.3% (TRAFFIC); trucks
  on the road now with stops projected late; yard geofence shows Swift Haul trailer APMTX00078
  inside the yard 4 hours early and not checked in, and Lonestar yard dwell up 59 minutes this week.

## Beat 2 (30 s): supervisor copilot
> **Why are we behind in the cooler?**

Expected: fulfillment agent, `diagnose_zone_backlog`: 702 cases left in COOLER, about 131 cases/hr
over the last 2 hours with 2 pickers, slots that can't cover their next pick; next action:
CRITICAL replenishment for those slots plus moving a picker into the cooler (approver: shift
supervisor). Under 100 words.

## Beat 3 (2 min): the disruption re-plan (headline)
> **The Lonestar trailer is late and we're short pickers tonight. Re-plan MTX.**

The `disruption_replan_pipeline` runs three assessors in parallel (dock/inbound, labor, waves)
and the re-plan writer produces:

**Situation**
- Trailer APMTX00063 (ASN0000039) carries 3 SKUs that tomorrow's orders need: Golden Fork Foil
  Wrap Sheet 48ct (361 cases short), Prairie Gold Honey Bun 6ct (109), Harvest Hill Mint Gum 24ct
  (27): **497 cases at risk across 74 order lines**.
- Night crew is 2 pickers; waves WMTX00059 (cutoff 04:00) and WMTX00060 (cutoff 05:30) need a
  crew of 3 and 5 to finish inside the night shift.
- Customer impact (`assess_route_otd_risk`): with 2 pickers, routes MTX-R07 to R12 leave late and
  **41 of 86 retail stops miss their receiving window tomorrow** (projected OTD 52.3%).

**Re-plan (each step with gain and approver)**
1. Door APMTX00063 now at MTX-IB02 (free 10:30-11:30), receive the 3 critical SKUs first and put
   them straight to pick faces. Gain: protects 497 cases / 74 lines. [Dock / yard lead]
2. Door the Coldline freezer trailer APMTX00064 at refrigerated door MTX-IB11 now. Gain: stops detention
   (175 min waiting). [Dock / yard lead]
3. Move freezer appointment APMTX00070 (10:45) off dry door MTX-IB01 to refrigerated MTX-IB07. Gain:
   cold-chain compliance (hard constraint). [Dock / yard lead]
4. Extend 3 day-shift pickers (Linh King, Keisha Lee, Sofia Thomas) 2 h into the night waves, about
   $32/h overtime each; flex two night loaders (Hannah Lopez, Priya Jackson) into picking for the
   first 3 hours. Gain: closes the 5.8 h gap with about 4 h of margin. [Shift supervisor; DC manager for overtime]
5. Release waves earliest-deadline-first: WMTX00057 -> 058 -> 059 -> 060. Gain: protects the
   03:00 and 04:00 routes first. [Shift supervisor]
6. Run CRITICAL replenishments before the waves reach those faces. [Inventory control lead]

**Before / after (stated assumptions)**

| KPI | Before | After re-plan | Assumption |
|---|---|---|---|
| Picker-hour gap (tomorrow's ship date) | -5.8 h | about +4.4 h | 3 pickers x 2 h OT + 2 loaders x 3 h flex, at 85% utilization |
| Cases at risk from the late trailer | 497 | 0 | critical SKUs received and cross-docked before 18:00 |
| Waves at risk of missing cutoff | 2 | 0 | OT + flex crew on waves 059/060 |
| Trailers in detention | 1 | 0 | freezer trailer doored now |
| Cold loads on ambient doors | 1 | 0 | appointment moved |
| Overtime cost | $0 | about $192 | 6 h at about $32/h |
| Customer stops missing their window | 41 of 86 (OTD 52.3%) | 0 (OTD 100%) | waves crewed like 5 pickers, PC*MILER drive times |

> **Propose those actions.**  then  **Approve the door change for APMTX00063.**

The specialists call `propose_action` (status PROPOSED with expected gain and approver role) and
the orchestrator calls `decide_action` only on explicit approval. Show `list_actions`.

## Beat 4 (45 s): slotting and integrity
> **Where are we wasting travel at MTX?**

Expected: slotting efficiency DRY 88.3%, COOLER 92.7%, FREEZER 95.1%; top 10 swaps save about
6.5 labor hours/week; example: move Red River Spring Water 16.9oz (47 picks/week) from MTX-D04-18-1
(244 ft) to golden-zone MTX-D02-05-2 (101 ft). Ergonomic flags for heavy fast movers.

> **Any inventory integrity problems I should count today?**

Expected: COOLER yogurt stored in a DRY reserve slot (MTX-D03-05-5, critical), one negative on-hand,
one over-capacity slot, over-allocated faces; prioritized cycle-count list.

## Beat 5 (30 s): across all three WMS platforms
> **Compare KPIs across our DCs and WMS platforms, and show interface problems.**

Expected: scorecard for 6 DCs (Manhattan Active, Blue Yonder, Argent); Blue Yonder UOM_MISMATCH
errors at MCA/MNY on the ORDER_RELEASE / ITEM_MASTER interfaces; field mapping example:
"What is EXPIRE_DTE in Blue Yonder?" -> `inventory.expiry_date`.

## Beat 6 (45 s): McLane delivery view (OTD, dwell, geofence, PC*MILER)
> **Why is restaurant OTD down at FDL?**

Expected (`delivery_otd_agent`, `get_otd_performance`): FDL restaurant OTD **68.0% this week vs
86.9% last week**; 144 of the late stops are LATE_DEPARTURE (trailers leaving after late waves), 20
CUSTOMER_DWELL. Network-wide this week: Retail 93.0%, Restaurant 78.4%. Next action: release FDL
waves earliest-deadline-first and crew them to cutoff (approver: shift supervisor), and send updated
ETAs to restaurants on late trucks (NOTIFY_CUSTOMER, transportation manager).

> **Is dwell time going up anywhere?**

Expected (`get_dwell_time_changes`): Lonestar Logistics at MTX, inbound yard dwell **120 -> 179 min
(+59)**, driven by gate-to-door wait (+33) and door-to-gate (+29); Taco Trail restaurants served by
FDL, stop dwell **37 -> 59 min** against a 36-minute standard, OTD 70.5%.

> **How many PC*MILER miles is route MTX-R07 tomorrow, and why is it always late?**

Expected: 319.8 practical miles, 7.9 drive hours (source PCMILER_SYNTH; live PC*MILER when
`PCMILER_API_KEY` is set); OTD 55.3% this week, late reason TRAFFIC: drive time runs about 28% over
PC*MILER (work zone), so the fix is a re-plan of the stop sequence or an earlier departure
(RESEQUENCE_ROUTE, transportation manager).

## Backup questions
- "Where is the order for Burger Barn at FDL?" (lookup_order)
- "Which trailers will be late this afternoon?" (predict_dock_arrivals)
- "Which SKUs are ordered together but slotted far apart?" (get_sku_affinity)
- "Top 5 SKUs by short cases last week across all DCs, as SQL." (data_analyst_agent)
- Upload a photo of a crushed case: "Should we ship this?" (multimodal damage check -> HOLD proposal)
- "Which trucks are in the MTX yard right now?" (get_geofence_activity: 7 trailers, detention risk
  on the Coldline freezer trailer, Swift Haul in the yard but not checked in)
- "Where is Taco Trail #2084 and when do they take deliveries?" (lookup_customer_site: geofence 90 m,
  window 08:30-09:30, 36.5 PC*MILER miles from FDL)
