# Hackathon prompt 3 (Warehouse Management), filled in for this project

Your section 3 prompt with the placeholders filled from the synthetic dataset. Paste it into
Gemini / Vertex AI Studio for the design narrative; the working implementation of the same design is
this repo (the agent's own system prompts are in `warehouse_agent/prompts.py`).

```text
<role>You are a warehouse operations and AI solutions lead for a high-volume distribution network
(dry, chilled, frozen) of 6 DCs (4 convenience-retail grocery DCs, 2 restaurant foodservice DCs)
with 500 SKUs (about 350 slotted per DC) and about 7,500 daily order lines (1,000-1,400 per DC).</role>

<context>
- Systems: WMS (Manhattan Active WM at MTX and MGA, Blue Yonder WMS at MCA and MNY, Argent at FDL
  and FOH) harmonized into one canonical model; labor management (engineered standards, schedules,
  call-outs); slotting data; inventory with lots and expiry; inbound ASNs and outbound waves; 28 dock
  doors per DC (refrigerated and ambient); equipment (RF, forklifts, pallet jacks).
- Pain points: pick-path inefficiency, poor slotting (DRY slotting efficiency 88%), labor imbalance
  (night call-outs leave a 5.8 picker-hour gap at MTX), dock congestion (trailers waiting 2-3 hours,
  a freezer load on an ambient door), inventory inaccuracy (record accuracy about 80%),
  shorts/mispicks, expiry/FEFO waste.
</context>

<task>Design an AI-driven warehouse assistant that:
1. Slotting: recommend SKU placement by velocity, cube, affinity, and ergonomics; quantify pick-travel savings.
2. Wave/task planning: sequence picks, batch orders, and balance labor across zones/shifts in real time.
3. Dock scheduling: predict inbound/outbound arrival times and assign doors to reduce dwell.
4. Inventory integrity: detect anomalies (negative stock, cycle-count variances, FEFO/expiry risk) and prioritize counts.
5. Supervisor copilot: answer questions ("Why are we behind in Zone C?") and suggest corrective actions.
</task>

<tools_and_data>Use: BigQuery (WMS/LMS data, dataset mclane_wms, 28 tables incl. route stops, geofence events and PC*MILER lanes), AlloyDB for operational
reads, Vertex AI (demand/velocity forecasting, anomaly detection, ETA prediction), Gemini (copilot via
Google ADK multi-agent on Agent Engine, surfaced in Gemini Enterprise; multimodal photo-based
damage/label checks), Pub/Sub (real-time events).
Sample data: synthetic, anchored to 2026-10-27 10:30, with planted problems: MTX night call-outs,
a late inbound trailer carrying 497 cases needed for tomorrow's orders, a detention-risk freezer
trailer, a double-booked door, expired lots, pick faces below min, mis-slotted fast movers, a Blue
Yonder UOM_MISMATCH interface spike, negative on-hand and cold product in an ambient slot.</tools_and_data>

<requirements>
- Respect safety, temperature-zone, and FEFO rules as hard constraints.
- Every recommendation shows rationale, expected gain (e.g., picks/hr, travel distance, dwell minutes), and who must approve.
- Keep supervisor responses under 100 words with a clear next action.
- State assumptions; flag data gaps.
</requirements>

<output_format>
1. Architecture and data flow
2. Capability-by-capability design with KPIs (units/labor hr, pick accuracy, dock dwell, inventory accuracy)
3. Demo scenario: mid-shift disruption (late inbound + labor shortfall) with AI re-plan
4. Implementation roadmap: hackathon MVP vs. 90-day pilot
5. Risks, change management, and success metrics
</output_format>
```

Where each output section lives in this repo:
1-2 -> [ARCHITECTURE.md](ARCHITECTURE.md), 3 -> [DEMO_SCRIPT.md](DEMO_SCRIPT.md),
4-5 -> [ROADMAP.md](ROADMAP.md).
