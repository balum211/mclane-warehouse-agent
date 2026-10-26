---
name: wms-demo-facts
description: Use when preparing or rehearsing the hackathon demo, or when you need the exact numbers the agent should produce for the planted MTX mid-shift disruption (late inbound + labor shortfall), without calling Gemini.
---

# Demo facts

Run `python .agents/skills/wms-demo-facts/scripts/demo_facts.py [DC]` (default MTX). It calls the
same tool functions the agents use and prints the key facts for each demo beat: labor gap,
the late trailer and the freight it carries, dock exceptions, wave sequence, slotting savings,
inventory anomalies and integration health.

Use the output to check the agent's answers during rehearsal and to fill in the before/after KPI
table in `docs/DEMO_SCRIPT.md`. If the numbers change after editing the generator, update the
demo script.
