"""End-to-end agent flow without calling Gemini.

A scripted fake model drives the real ADK runtime: the orchestrator transfers to a pipeline, the
parallel collectors call the real tools against SQLite, and the writer receives their output
through session state. This proves the wiring (transfers, tool schemas, output_keys, instruction
providers) before spending tokens on a live model.
"""

from __future__ import annotations

import asyncio
import inspect
from typing import AsyncGenerator

from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.adk.runners import InMemoryRunner
from google.genai import types

ARG_DEFAULTS = {"dc_id": "MTX", "zone": "DRY", "sku_or_keyword": "fries", "term": "sku", "customer": "Taco Trail"}
ROUTES = {"re-plan": "disruption_replan_pipeline", "briefing": "shift_briefing_pipeline",
          "behind": "fulfillment_agent", "otd": "delivery_otd_agent"}


class ScriptedLlm(BaseLlm):
    model: str = "scripted"
    instructions_seen: list = []

    async def generate_content_async(self, llm_request: LlmRequest, stream: bool = False
                                     ) -> AsyncGenerator[LlmResponse, None]:
        tools = llm_request.tools_dict
        system = str(llm_request.config.system_instruction or "")
        self.instructions_seen.append(system)
        called = {p.function_response.name for c in llm_request.contents for p in (c.parts or [])
                  if p.function_response}
        user_text = " ".join(p.text for c in llm_request.contents if c.role == "user"
                             for p in (c.parts or []) if p.text).lower()
        is_orchestrator = "Warehouse Operations Copilot" in system
        if is_orchestrator and "transfer_to_agent" not in called:
            target = next((a for k, a in ROUTES.items() if k in user_text), "inventory_agent")
            yield _call("transfer_to_agent", {"agent_name": target})
            return
        for name, tool in tools.items():
            if name in ("transfer_to_agent", "propose_action", "decide_action", "list_actions", "lookup_order") \
                    or name in called:
                continue
            sig = inspect.signature(tool.func)
            args = {k: ARG_DEFAULTS[k] for k, p in sig.parameters.items()
                    if p.default is inspect.Parameter.empty and k in ARG_DEFAULTS}
            if "appointment_id" in sig.parameters:
                from warehouse_agent.tools import get_dock_exceptions
                args["appointment_id"] = get_dock_exceptions("MTX")["waiting_for_door"][0]["appointment_id"]
            if name == "get_route_miles":
                args["route_id"] = "MTX-R07"
            yield _call(name, args)
            return
        yield LlmResponse(content=types.Content(role="model", parts=[
            types.Part(text=f"SCRIPTED SUMMARY from tools: {sorted(called - {'transfer_to_agent'})}")]))


def _call(name: str, args: dict) -> LlmResponse:
    return LlmResponse(content=types.Content(role="model", parts=[
        types.Part(function_call=types.FunctionCall(name=name, args=args))]))


async def _run(message: str):
    from warehouse_agent.agent import build_root_agent

    llm = ScriptedLlm()
    llm.instructions_seen = []
    runner = InMemoryRunner(agent=build_root_agent(model=llm), app_name="wms_test")
    session = await runner.session_service.create_session(app_name="wms_test", user_id="u1")
    events = []
    async for ev in runner.run_async(user_id="u1", session_id=session.id,
                                     new_message=types.Content(role="user", parts=[types.Part(text=message)])):
        events.append(ev)
    session = await runner.session_service.get_session(app_name="wms_test", user_id="u1", session_id=session.id)
    return events, session, llm


def _errors(events):
    return [p.function_response.response for e in events for p in (e.content.parts if e.content else [])
            if p.function_response and isinstance(p.function_response.response, dict)
            and p.function_response.response.get("status") == "error"]


def test_disruption_replan_pipeline_end_to_end():
    events, session, llm = asyncio.run(_run("Inbound trailer is late and we're short pickers at MTX, re-plan tonight"))
    authors = {e.author for e in events}
    assert {"replan_dock_agent", "replan_labor_agent", "replan_waves_agent", "replan_otd_agent",
            "replan_writer"} <= authors
    for key in ("replan_dock", "replan_labor", "replan_waves", "replan_otd"):
        assert "SCRIPTED SUMMARY" in session.state[key]
    assert "assess_inbound_impact" in session.state["replan_dock"]
    writer_prompt = llm.instructions_seen[-1]
    assert "Disruption re-plan" in writer_prompt and "forecast_labor_requirement" in writer_prompt
    assert "assess_route_otd_risk" in writer_prompt
    assert not _errors(events)


def test_shift_briefing_pipeline_end_to_end():
    events, session, _ = asyncio.run(_run("Give me the shift briefing for MTX"))
    for key in ("inventory_snapshot", "fulfillment_snapshot", "labor_snapshot", "dock_snapshot", "delivery_snapshot"):
        assert key in session.state
    assert any(e.author == "briefing_writer" for e in events)
    assert not _errors(events)


def test_zone_question_routes_to_fulfillment():
    events, _, _ = asyncio.run(_run("Why are we behind in Zone C?"))
    assert any(e.author == "fulfillment_agent" for e in events)
    assert not _errors(events)


def test_otd_question_routes_to_delivery_agent_and_calls_every_tool():
    events, _, _ = asyncio.run(_run("Why is restaurant OTD down at FDL?"))
    assert any(e.author == "delivery_otd_agent" for e in events)
    called = {p.function_call.name for e in events for p in (e.content.parts if e.content else []) if p.function_call}
    from warehouse_agent.tools import DELIVERY_TOOLS
    assert {f.__name__ for f in DELIVERY_TOOLS} <= called
    assert not _errors(events)
