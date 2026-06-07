"""
Multi-Agent System
==================
Architecture: Supervisor pattern using LangGraph + LangChain

Agents:
  - Calculator Agent : Arithmetic, formulas, cost breakdowns
  - Mall Agent       : Store search, menus, order placement
  - Browser Agent    : Full browser control via Playwright
  - Search Agent     : AI news & web search (can delegate to Browser Agent)

Flow:
  Every user query enters the Orchestrator, which classifies the intent
  and routes it to the correct agent.  Mall orders auto-hand-off to the
  Calculator subgraph for totals.

                       ┌─────────────┐
                       │    START    │
                       └──────┬──────┘
                              │
                       ┌──────▼──────┐
                       │ Orchestrator│  ← classifies & routes
                       └──────┬──────┘
          ┌────────────┬───────┴───────┬────────────┐
   ┌──────▼──────┐ ┌───▼────┐ ┌───────▼──────┐ ┌───▼────┐
   │  Calculator │ │  Mall  │ │   Browser    │ │ Search │
   └──────┬──────┘ └───┬────┘ └───────┬──────┘ └───┬────┘
          │             │              │              │
          │      ┌──────▼──────┐       │              │
          │      │  Calculator │       │              │
          │      │  Subgraph   │       │              │
          │      └──────┬──────┘       │              │
          └─────────────┴──────────────┴──────────────┘
                               │
                        ┌──────▼──────┐
                        │     END     │
                        └─────────────┘
"""

import json
from typing import TypedDict, Annotated

from langchain_core.messages import BaseMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages

from config import AgentConfig
from ..agent.orchestrator import OrchestratorAgent
from ..core.logger import get_agent_logger

logger = get_agent_logger("workflow")


# =========================================================
# STATE DEFINITIONS
# =========================================================

class AgentState(TypedDict):
    query:               str    # raw user input
    route_to:            str    # agent the orchestrator decided to use
    forced_agent:        str    # user-selected agent override; empty = auto
    orchestrator_route:  str    # what the orchestrator recommends
    suggested_agent:     str    # non-empty when forced != orchestrator
    result:              dict   # final output returned to the user
    error:               str    # error message if something goes wrong
    history:             list   # conversation history for multi-turn context
    last_agent:          str    # which agent handled the previous turn


class CalculationState(TypedDict):
    items:       list[dict]
    tax_rate:    float
    messages:    Annotated[list[BaseMessage], add_messages]
    calc_result: dict


# =========================================================
# INITIALISATION
# =========================================================

_config       = AgentConfig()
_orchestrator = OrchestratorAgent(_config)

AGENTS = _orchestrator.registry


# =========================================================
# CALCULATOR SUBGRAPH
# =========================================================
# Invoked internally when a mall order is confirmed.
# Computes subtotal, tax, and grand total via the Calculator agent.

def _build_calculator_subgraph():

    def calc_entry(state: CalculationState) -> CalculationState:
        items    = state.get("items", [])
        tax_rate = state.get("tax_rate", 0.09)

        item_lines = "\n".join(
            f"- {i['name']}: {i['price']} {i.get('currency', 'USD')} x {i.get('quantity', 1)}"
            for i in items
        )
        prompt = (
            f"I have an order with the following items:\n{item_lines}\n\n"
            f"Please calculate:\n"
            f"1. The subtotal (sum of all items)\n"
            f"2. Tax at {tax_rate * 100:.1f}%\n"
            f"3. The grand total including tax\n"
            f"Show each step."
        )

        result      = AGENTS["calculator"].run(prompt)
        calc_result = {"status": "ok", "summary": ""}

        for msg in reversed(result.get("messages", [])):
            if type(msg).__name__ == "AIMessage" and msg.content:
                calc_result["summary"] = msg.content
                break

        return {**state, "messages": result.get("messages", []), "calc_result": calc_result}

    sub = StateGraph(CalculationState)
    sub.add_node("calc_entry", calc_entry)
    sub.add_edge(START, "calc_entry")
    sub.add_edge("calc_entry", END)
    return sub.compile()


_calculator_subgraph = _build_calculator_subgraph()


# =========================================================
# HELPERS
# =========================================================

def _extract_confirmed_items(result: dict) -> list[dict]:
    """
    Scan mall agent messages for a confirmed order.
    Returns line items only when status="confirmed" AND the AI used [TOTAL_REQUESTED].
    """
    confirmed_data = None

    for msg in result.get("messages", []):
        if type(msg).__name__ != "ToolMessage":
            continue

        content = msg.content
        if isinstance(content, list):
            data = content[0] if content else {}
        elif isinstance(content, dict):
            data = content
        elif isinstance(content, str):
            try:
                data = json.loads(content)
            except (ValueError, TypeError):
                continue
        else:
            continue

        if isinstance(data, list):
            data = data[0] if data else {}

        if not isinstance(data, dict):
            continue

        if data.get("status") == "confirmed":
            confirmed_data = data

    if not confirmed_data:
        return []

    price    = confirmed_data.get("price", 0.0)
    quantity = confirmed_data.get("quantity", 1)

    if not price:
        logger.warning(
            f"[_extract_confirmed_items] price missing from confirmed order — "
            f"handoff skipped. data: {confirmed_data}"
        )
        return []

    for msg in result.get("messages", []):
        if type(msg).__name__ == "AIMessage" and "[TOTAL_REQUESTED]" in (msg.content or ""):
            return [{
                "name":     confirmed_data.get("item", ""),
                "price":    price,
                "currency": confirmed_data.get("currency", "USD"),
                "quantity": quantity,
            }]

    return []


_CONFIRMATION_WORDS = {
    "yes", "ok", "confirm", "go ahead", "sure", "yep", "yeah", "proceed", "do it", "place it",
    "no", "cancel", "nope",
}


# =========================================================
# NODES
# =========================================================

def orchestrator_node(state: AgentState) -> AgentState:
    """
    Supervisor node — entry point for every user query.
    Classifies the intent and sets route_to in state.
    Respects forced_agent override and detects mismatches for suggestions.
    """
    query        = state["query"].strip().lower()
    last_agent   = state.get("last_agent", "none")
    forced_agent = state.get("forced_agent", "")

    if query in _CONFIRMATION_WORDS and last_agent != "none":
        orchestrator_route = last_agent
    else:
        orchestrator_route = _orchestrator.classify(query, last_agent=last_agent)

    if forced_agent and forced_agent in AGENTS:
        route_to = forced_agent
    else:
        route_to = orchestrator_route

    suggested_agent = ""
    if (
        forced_agent
        and forced_agent in AGENTS
        and orchestrator_route not in ("unknown", "fallback", "")
        and orchestrator_route != forced_agent
    ):
        suggested_agent = orchestrator_route

    logger.info(
        f"[route] query='{query}' | last={last_agent} | "
        f"forced={forced_agent or 'none'} | route={route_to} | suggest={suggested_agent or 'none'}"
    )

    return {
        **state,
        "route_to":           route_to,
        "orchestrator_route": orchestrator_route,
        "suggested_agent":    suggested_agent,
    }


def calculator_node(state: AgentState) -> AgentState:
    """Runs the Calculator agent for math queries."""
    try:
        result = AGENTS["calculator"].run(state["query"], state.get("history", []))
        return {**state, "result": result, "error": "", "last_agent": "calculator"}
    except Exception as e:
        logger.error(f"[calculator_node] {e}")
        return {**state, "result": {}, "error": str(e)}


def mall_node(state: AgentState) -> AgentState:
    """
    Runs the Mall agent for shopping queries.
    Auto-hands-off to Calculator when an order is confirmed.
    """
    try:
        result = AGENTS["mall"].run(state["query"], state.get("history", []))
        items  = _extract_confirmed_items(result)

        if items:
            item_labels = [
                f"{i['quantity']}x {i['name']} @ {i['price']} {i['currency']}"
                for i in items
            ]
            logger.info(f"[handoff] mall → calculator | items: {item_labels}")

            tax_rate   = getattr(_config, "tax_rate", 0.09)
            calc_state = _calculator_subgraph.invoke({
                "items":       items,
                "tax_rate":    tax_rate,
                "messages":    [],
                "calc_result": {},
            })
            result["calc_result"] = calc_state["calc_result"]
            logger.info(
                f"[handoff] calculator complete | "
                f"summary: {result['calc_result'].get('summary', '')[:80]}"
            )
        else:
            logger.debug("[handoff] no confirmed order — calculator not invoked")

        return {**state, "result": result, "error": "", "last_agent": "mall"}

    except Exception as e:
        logger.error(f"[mall_node] {e}")
        return {**state, "result": {}, "error": str(e)}


def browser_node(state: AgentState) -> AgentState:
    """Runs the Browser Agent for website navigation and interaction tasks."""
    try:
        result = AGENTS["browser"].run(state["query"], state.get("history", []))
        return {**state, "result": result, "error": "", "last_agent": "browser"}
    except Exception as e:
        logger.error(f"[browser_node] {e}")
        return {**state, "result": {}, "error": str(e)}


def search_node(state: AgentState) -> AgentState:
    """Runs the Search Agent for AI news, web search, and knowledge queries."""
    try:
        result = AGENTS["search"].run(state["query"], state.get("history", []))
        return {**state, "result": result, "error": "", "last_agent": "search"}
    except Exception as e:
        logger.error(f"[search_node] {e}")
        return {**state, "result": {}, "error": str(e)}


def fallback_node(state: AgentState) -> AgentState:
    """Catches queries that couldn't be routed to any known agent."""
    return {
        **state,
        "result": {},
        "error": (
            f"No agent found for: '{state['query']}'. "
            f"Available agents: {list(AGENTS.keys())}"
        ),
    }


# =========================================================
# ROUTER
# =========================================================

def route_query(state: AgentState) -> str:
    """Conditional edge — maps route_to value to the next node name."""
    return _orchestrator.route(state["route_to"])


# =========================================================
# GRAPH BUILDER
# =========================================================

def build_graph():
    """
    Assembles and compiles the full multi-agent graph.

    Nodes:   orchestrator, calculator, mall, browser, search, fallback
    Edges:   START → orchestrator → (conditional) → agent → END
    """
    graph = StateGraph(AgentState)

    graph.add_node("orchestrator", orchestrator_node)
    graph.add_node("calculator",   calculator_node)
    graph.add_node("mall",         mall_node)
    graph.add_node("browser",      browser_node)
    graph.add_node("search",       search_node)
    graph.add_node("fallback",     fallback_node)

    graph.add_edge(START, "orchestrator")

    graph.add_conditional_edges(
        "orchestrator",
        route_query,
        {
            "calculator": "calculator",
            "mall":       "mall",
            "browser":    "browser",
            "search":     "search",
            "unknown":    "search",   # safety net — search is the open fallback
            "fallback":   "fallback",
        },
    )

    graph.add_edge("calculator", END)
    graph.add_edge("mall",       END)
    graph.add_edge("browser",    END)
    graph.add_edge("search",     END)
    graph.add_edge("fallback",   END)

    return graph.compile()
