"""McLane Warehouse Operations Copilot: an ADK multi-agent system over harmonized WMS data.

Agent tree
----------
warehouse_ops_orchestrator (LlmAgent, routes requests)
 |- inventory_agent          stock, FEFO / expiry, replenishment, stockout risk, cycle counts
 |- slotting_agent           velocity vs travel, re-slot swaps, space utilization
 |- fulfillment_agent        orders, waves vs cutoff, short picks, wave release sequencing
 |- labor_agent              performance vs engineered standards, labor gap, rosters
 |- dock_yard_agent          appointments, detention, door conflicts, cold-chain door checks
 |- wms_integration_agent    Manhattan Active / Blue Yonder / Argent mapping, interface health, KPIs
 |- data_analyst_agent       guarded read-only SQL for ad-hoc questions
 |- shift_briefing_pipeline  SequentialAgent
 |    |- briefing_collectors ParallelAgent (inventory, fulfillment, labor, dock snapshots)
 |    '- briefing_writer     writes the start-of-shift briefing from session state
 '- disruption_replan_pipeline  SequentialAgent (late inbound + labor shortfall, mid-shift)
      |- replan_assessors    ParallelAgent (dock/inbound impact, labor gap, wave risk)
      '- replan_writer       writes the re-plan with gains, approvers and before/after KPIs

Run locally:  adk web .   (from the repo root)   or   adk run warehouse_agent
"""

from __future__ import annotations

from google.adk.agents import LlmAgent, ParallelAgent, SequentialAgent
from google.adk.agents.readonly_context import ReadonlyContext
from google.genai import types

from . import prompts
from .config import MODEL, SNAPSHOT_MODEL, TEMPERATURE
from .tools import (ANALYTICS_TOOLS, DOCK_TOOLS, FULFILLMENT_TOOLS, INTEGRATION_TOOLS, INVENTORY_TOOLS,
                                   LABOR_TOOLS, SLOTTING_TOOLS, assess_inbound_impact, decide_action,
                                   forecast_labor_requirement, get_dock_exceptions, get_expiring_inventory,
                                   get_order_fulfillment_summary, get_replenishment_needs, get_shift_roster,
                                   get_stockout_risk, get_wave_progress, get_wms_landscape, list_actions,
                                   predict_dock_arrivals, propose_action, recommend_door, recommend_wave_release)
from .tools.common import now

GEN_CONFIG = types.GenerateContentConfig(temperature=TEMPERATURE)


def _clock() -> dict:
    t = now()
    return {"today": t.strftime("%A %Y-%m-%d"), "now": t.strftime("%H:%M")}


def _with_shared(template: str):
    """Instruction provider that fills the shared operating context and the demo clock."""

    def provider(_ctx: ReadonlyContext) -> str:
        return template.format(shared=prompts.SHARED_CONTEXT.format(**_clock()))

    return provider


def _specialist(name: str, description: str, template: str, tools: list, model) -> LlmAgent:
    return LlmAgent(
        name=name,
        model=model,
        description=description,
        instruction=_with_shared(template),
        tools=tools + [propose_action],
        generate_content_config=GEN_CONFIG,
    )


def _snapshot(name: str, slice_desc: str, tools: list, output_key: str, model) -> LlmAgent:
    def provider(_ctx: ReadonlyContext) -> str:
        return prompts.SNAPSHOT.format(slice=slice_desc, **_clock())

    return LlmAgent(name=name, model=model, description=f"Collects {slice_desc}",
                    instruction=provider, tools=tools, output_key=output_key,
                    generate_content_config=GEN_CONFIG)


def _briefing_instruction(ctx: ReadonlyContext) -> str:
    s = ctx.state
    return prompts.BRIEFING_WRITER.format(
        inventory=s.get("inventory_snapshot", "(not collected)"),
        fulfillment=s.get("fulfillment_snapshot", "(not collected)"),
        labor=s.get("labor_snapshot", "(not collected)"),
        dock=s.get("dock_snapshot", "(not collected)"),
        **_clock())


def _replan_instruction(ctx: ReadonlyContext) -> str:
    s = ctx.state
    return prompts.REPLAN_WRITER.format(
        dock=s.get("replan_dock", "(not collected)"),
        labor=s.get("replan_labor", "(not collected)"),
        waves=s.get("replan_waves", "(not collected)"),
        **_clock())


def build_root_agent(model=None, snapshot_model=None) -> LlmAgent:
    """Build the agent tree. `model` accepts a model name or an ADK BaseLlm (tests pass a fake)."""
    model = model or MODEL
    snapshot_model = snapshot_model or (model if not isinstance(model, str) else SNAPSHOT_MODEL)
    inventory_agent = _specialist(
        "inventory_agent",
        "Inventory control: stock positions, expiring lots (FEFO), replenishment, stockout risk, cycle counts.",
        prompts.INVENTORY, INVENTORY_TOOLS, model)
    slotting_agent = _specialist(
        "slotting_agent",
        "Slotting: pick velocity vs travel distance, re-slot swap recommendations, space utilization.",
        prompts.SLOTTING, SLOTTING_TOOLS, model)
    fulfillment_agent = _specialist(
        "fulfillment_agent",
        "Fulfillment: order status, wave progress vs cutoff, short picks, wave release sequencing, order lookup.",
        prompts.FULFILLMENT, FULFILLMENT_TOOLS, model)
    labor_agent = _specialist(
        "labor_agent",
        "Labor: productivity vs engineered standards, labor required vs scheduled, call-outs, rosters.",
        prompts.LABOR, LABOR_TOOLS, model)
    dock_agent = _specialist(
        "dock_yard_agent",
        "Dock and yard: appointments, late carriers, detention, door conflicts, cold-chain door checks.",
        prompts.DOCK, DOCK_TOOLS, model)
    integration_agent = _specialist(
        "wms_integration_agent",
        "Cross-WMS: Manhattan Active / Blue Yonder / Argent landscape, interface errors, field mapping, KPIs.",
        prompts.INTEGRATION, INTEGRATION_TOOLS, model)
    analyst_agent = LlmAgent(
        name="data_analyst_agent",
        model=model,
        description="Answers ad-hoc questions with guarded read-only SQL over the canonical WMS tables.",
        instruction=_with_shared(prompts.ANALYST),
        tools=ANALYTICS_TOOLS,
        generate_content_config=GEN_CONFIG,
    )

    collectors = ParallelAgent(
        name="briefing_collectors",
        description="Collects inventory, fulfillment, labor and dock status in parallel.",
        sub_agents=[
            _snapshot("inventory_snapshot_agent",
                      "inventory risks: expiring lots in 2 days, CRITICAL/HIGH replenishments, tomorrow's stockout risks",
                      [get_expiring_inventory, get_replenishment_needs, get_stockout_risk], "inventory_snapshot", snapshot_model),
            _snapshot("fulfillment_snapshot_agent",
                      "fulfillment: tomorrow's order/pick progress, fill-rate trend, waves at risk of missing cutoff",
                      [get_order_fulfillment_summary, get_wave_progress], "fulfillment_snapshot", snapshot_model),
            _snapshot("labor_snapshot_agent",
                      "labor: required vs available picker hours for tomorrow's ship date, gap, call-outs",
                      [forecast_labor_requirement], "labor_snapshot", snapshot_model),
            _snapshot("dock_snapshot_agent",
                      "dock: today's exceptions (temp mismatches, trailers waiting, door conflicts, late carriers)",
                      [get_dock_exceptions], "dock_snapshot", snapshot_model),
        ],
    )
    briefing_writer = LlmAgent(
        name="briefing_writer",
        model=model,
        description="Writes the start-of-shift briefing from the collected snapshots.",
        instruction=_briefing_instruction,
        generate_content_config=GEN_CONFIG,
    )
    shift_briefing = SequentialAgent(
        name="shift_briefing_pipeline",
        description="Start-of-shift briefing / overall DC status: parallel data collection, then a written briefing.",
        sub_agents=[collectors, briefing_writer],
    )

    assessors = ParallelAgent(
        name="replan_assessors",
        description="Assesses dock/inbound impact, labor gap and wave risk in parallel.",
        sub_agents=[
            _snapshot("replan_dock_agent",
                      "dock and inbound: late or waiting trailers, the freight they carry that tomorrow's orders need "
                      "(cases at risk, orders affected), predicted arrivals, and a free compatible door for the most "
                      "critical trailer",
                      [assess_inbound_impact, get_dock_exceptions, predict_dock_arrivals, recommend_door],
                      "replan_dock", snapshot_model),
            _snapshot("replan_labor_agent",
                      "labor: required vs available picker hours for tomorrow's ship date by zone, call-outs, and "
                      "named candidates to close the gap with overtime cost",
                      [forecast_labor_requirement, get_shift_roster], "replan_labor", snapshot_model),
            _snapshot("replan_waves_agent",
                      "waves: progress vs cutoff, waves at risk, and the recommended release sequence with the "
                      "minimum crew needed",
                      [get_wave_progress, recommend_wave_release], "replan_waves", snapshot_model),
        ],
    )
    replan_writer = LlmAgent(
        name="replan_writer",
        model=model,
        description="Writes the disruption re-plan from the assessments.",
        instruction=_replan_instruction,
        generate_content_config=GEN_CONFIG,
    )
    disruption_replan = SequentialAgent(
        name="disruption_replan_pipeline",
        description="Mid-shift disruption (late inbound, labor shortfall): parallel impact assessment, then a re-plan.",
        sub_agents=[assessors, replan_writer],
    )

    return LlmAgent(
        name="warehouse_ops_orchestrator",
        model=model,
        description="McLane warehouse operations copilot across Manhattan Active, Blue Yonder and Argent DCs.",
        instruction=_with_shared(prompts.ORCHESTRATOR),
        tools=[get_wms_landscape, list_actions, decide_action],
        sub_agents=[inventory_agent, slotting_agent, fulfillment_agent, labor_agent, dock_agent,
                    integration_agent, analyst_agent, shift_briefing, disruption_replan],
        generate_content_config=GEN_CONFIG,
    )


root_agent = build_root_agent()
