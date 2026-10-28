---
name: wms-demo-facts
description: Use when preparing or rehearsing the hackathon demo, or when you need the exact numbers the agent should produce for the planted MTX mid-shift disruption (late inbound + labor shortfall) and the delivery facts (Retail vs Restaurant OTD, dwell changes, geofence flags, PC*MILER miles), without calling Gemini.
---

# Demo facts

Run `python .agents/skills/wms-demo-facts/scripts/demo_facts.py [DC]` (default MTX). It calls the
same tool functions the agents use and prints the key facts for each demo beat: labor gap,
the late trailer and the freight it carries, dock exceptions, wave sequence, slotting savings,
inventory anomalies and integration health, then the delivery side: Retail vs Restaurant OTD,
the worst route, customer windows at risk from tonight's waves (before and after the re-plan), dwell
changes, yard geofence flags and PC*MILER miles.

Use the output to check the agent's answers during rehearsal and to fill in the before/after KPI
table in `docs/DEMO_SCRIPT.md`. If the numbers change after editing the generator, update the
demo script.
