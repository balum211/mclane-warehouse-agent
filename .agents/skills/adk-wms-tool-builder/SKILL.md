---
name: adk-wms-tool-builder
description: Use when adding a new capability, tool or specialist agent to the McLane warehouse ADK agent (for example "add a temperature excursion tool" or "add a returns agent"). Covers the tool function contract, wiring into agent.py and prompts.py, and the tests to add.
---

# Adding a tool or specialist to the warehouse agent

## Steps
1. **Spec first.** If this is a new capability, run `/speckit.specify` and `/speckit.plan` so it has
   a spec in `specs/`. Small tool additions can reference an existing spec.
2. **Schema.** If you need new data, add the table to `warehouse_agent/schema.py` (logical types
   STRING, INT, FLOAT, DATE, DATETIME, plus a primary key), generate it in
   `warehouse_data/generate.py`, and regenerate `sql/schema_*.sql` (see the `wms-synthetic-data` skill).
3. **Tool function** in the right `warehouse_agent/tools/<domain>.py`, following
   `references/tool_template.py`:
   - plain-typed args with defaults, `dc_id` first for DC-scoped tools;
   - Google-style docstring: one-line summary, when to use it, `Args:`, `Returns:` (ADK turns this
     into the function declaration the model sees, so write it for the model);
   - return `ok(...)` or `error("...")`, never raise for bad input;
   - portable SQL only (skill `wms-portable-sql`);
   - quantify impact (cases, hours, dollars, minutes) in the result.
4. **Export** it from `warehouse_agent/tools/__init__.py` and add it to the domain list
   (`INVENTORY_TOOLS`, `DOCK_TOOLS`, ...).
5. **Prompt.** Tell the specialist when to use it in `warehouse_agent/prompts.py`. If it is a new
   specialist, add `_specialist(...)` in `build_root_agent()` and a routing line in `ORCHESTRATOR`.
6. **Tests.** Add the call to `CALLS` in `tests/test_portability.py`, a behaviour test in
   `tests/test_tools.py`, and run `make test`. For routing, add a case to `tests/test_agent_flow.py`.
7. **Try it** with `adk web .` and a real question.

## Constraints
- Recommendations never execute changes: use `propose_action` with an `expected_gain`.
- Respect safety, temperature-zone and FEFO rules as hard constraints.
