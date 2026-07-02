"""Claude agent for the OBR macroeconomic model emulator.

A tool-using Claude agent (manual agentic loop) whose tools wrap the project's
pre-computed model data — scenarios, variables, equations — so a user can ask
questions in natural language and get grounded answers. The tools read the
inlined JSON the dashboard already builds, so they are instant (no slow solves).
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import anthropic
from dotenv import load_dotenv

load_dotenv()  # read ANTHROPIC_API_KEY (and ANTHROPIC_MODEL) from .env

DATA = Path(__file__).resolve().parents[1] / "dashboard" / "public" / "data"
MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-opus-4-8")

_model = json.loads((DATA / "model_data.json").read_text())
_explorer = json.loads((DATA / "explorer_data.json").read_text())
_items = _model["items"]
_by_code = {it["code"]: it for it in _items}


# --------------------------------------------------------------------------
# tools — each returns a JSON-serialisable result
# --------------------------------------------------------------------------
def list_scenarios() -> dict:
    out = []
    for s in _explorer["scenarios"]:
        out.append({
            "id": s["id"], "name": s["name"], "tag": s["tag"],
            "shock": s["shock"], "closure": s["closure"],
            "variables_available": list(s["series"].keys()),
        })
    return {"scenarios": out, "note": _explorer["meta"].get("note", "")}


def scenario_impact(scenario_id: str, variable_code: str = "GDPM") -> dict:
    sc = next((s for s in _explorer["scenarios"] if s["id"] == scenario_id), None)
    if sc is None:
        return {"error": f"unknown scenario '{scenario_id}'",
                "valid": [s["id"] for s in _explorer["scenarios"]]}
    if not sc["series"]:
        return {"scenario": sc["name"],
                "note": "This scenario produced no material change in the tracked "
                        "variables under its closure (a known limitation)."}
    if variable_code not in sc["series"]:
        return {"scenario": sc["name"],
                "error": f"variable '{variable_code}' not available for this scenario",
                "available": list(sc["series"].keys())}
    meta = next((v for v in _explorer["variables"] if v["code"] == variable_code), {})
    return {
        "scenario": sc["name"], "shock": sc["shock"], "closure": sc["closure"],
        "variable": variable_code, "label": meta.get("label", variable_code),
        "unit": meta.get("unit", ""),
        "periods": _explorer["periods"],
        "delta_vs_baseline": sc["series"][variable_code],
        "note": "Emulator output (15 Oct 2025 OBR model code), illustrative — not an OBR forecast.",
    }


def search_variables(query: str, limit: int = 12) -> dict:
    q = query.lower()
    hits = [it for it in _items
            if q in it["code"].lower() or q in (it["desc"] or "").lower()]
    return {"count": len(hits), "showing": min(len(hits), limit), "matches": [
        {"code": it["code"], "description": it["desc"], "group": it["group"],
         "type": it["type"], "ons": it["ons"]}
        for it in hits[:limit]]}


def get_equation(code: str) -> dict:
    it = _by_code.get(code)
    if it is None:
        return {"error": f"unknown variable code '{code}'"}
    return {"code": it["code"], "description": it["desc"], "type": it["type"],
            "group": it["group"], "eviews": it["eq"] or "(exogenous — no equation)",
            "transpiled_python": it["py"] or ""}


def model_overview() -> dict:
    return {
        "what": "An independent Python re-implementation of the OBR's published "
                "macroeconomic model (15 October 2025 code).",
        "equations": 372, "groups": 16, "variables": len(_items),
        "solver": "Gauss-Seidel simultaneous-equation solver",
        "honest_limits": [
            "Results use the user's own assumptions and are NOT OBR or Treasury forecasts.",
            "Only ~10 headline channels are genuinely computed; some (exports, imports, "
            "CPI) are held at the OBR baseline value.",
            "The forecasting framework reproduces the OBR's published path within ~10% on "
            "the macro core (GDP, consumption, investment, employment, prices, balances).",
        ],
    }


TOOLS = [
    {"name": "model_overview", "description": "What this model is, its scale, and its honest limitations. Call for 'what is this' questions.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "list_scenarios", "description": "List the available pre-computed policy scenarios and which variables each one moves.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "scenario_impact", "description": "Get the modelled quarter-by-quarter impact of a scenario on a variable (delta vs an unchanged baseline).",
     "input_schema": {"type": "object", "properties": {
         "scenario_id": {"type": "string", "description": "e.g. gov_spend, corp_cut, corp_rise, gov_invest, austerity"},
         "variable_code": {"type": "string", "description": "e.g. GDPM, CONS, IF, IBUS. Defaults to GDPM."}},
         "required": ["scenario_id"]}},
    {"name": "search_variables", "description": "Search the 636 model variables by code or description; returns code, meaning, group, type, ONS series.",
     "input_schema": {"type": "object", "properties": {
         "query": {"type": "string"}, "limit": {"type": "integer"}}, "required": ["query"]}},
    {"name": "get_equation", "description": "Get a variable's published EViews equation and the transpiled Python for a given model code.",
     "input_schema": {"type": "object", "properties": {"code": {"type": "string"}}, "required": ["code"]}},
]

_DISPATCH = {
    "model_overview": lambda **k: model_overview(),
    "list_scenarios": lambda **k: list_scenarios(),
    "scenario_impact": lambda **k: scenario_impact(**k),
    "search_variables": lambda **k: search_variables(**k),
    "get_equation": lambda **k: get_equation(**k),
}


def execute_tool(name: str, tool_input: dict) -> dict:
    try:
        return _DISPATCH[name](**tool_input)
    except Exception as e:  # surface tool errors to the model, don't crash
        return {"error": f"{type(e).__name__}: {e}"}


SYSTEM = """You are the assistant for an open-source emulator of the OBR (UK Office \
for Budget Responsibility) macroeconomic model — the same equations the Budget \
Responsibility Committee uses to build the UK economy forecast, re-implemented in Python.

Use the tools to answer with real model data; never invent numbers. When a user asks \
about a policy scenario, call scenario_impact; about what a variable means or its \
equation, call search_variables / get_equation; about the model itself, call model_overview.

Be precise and honest. Always make clear that results are emulator output under the \
user's own assumptions — not OBR or Treasury forecasts — and flag known limitations \
(e.g. only the macro core is genuinely computed). Quote figures with their units and the \
quarter. Keep answers concise and lead with the headline number."""


def respond(messages: list, max_rounds: int = 6) -> tuple[str, list]:
    """Run the agentic tool loop. Returns (final_text, updated_messages)."""
    client = anthropic.Anthropic()
    response = None
    for _ in range(max_rounds):
        response = client.messages.create(
            model=MODEL,
            max_tokens=8000,
            system=SYSTEM,
            tools=TOOLS,
            thinking={"type": "adaptive"},
            output_config={"effort": "medium"},
            messages=messages,
        )
        messages.append({"role": "assistant", "content": response.content})
        tool_uses = [b for b in response.content if b.type == "tool_use"]
        if not tool_uses:
            break
        messages.append({"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": b.id,
             "content": json.dumps(execute_tool(b.name, b.input))}
            for b in tool_uses]})
    text = "\n".join(b.text for b in (response.content if response else []) if b.type == "text")
    return text.strip() or "(no answer)", messages
