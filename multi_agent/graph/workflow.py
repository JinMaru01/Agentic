"""
Multi-Agent System — Proof of Concept
======================================
Architecture: Supervisor pattern using LangGraph + LangChain

Agents:
  - Calculator Agent  : Handles arithmetic and order cost calculations
  - Mall Agent        : Handles product search, store lookup, and order booking

Flow:
  Every user query enters the Orchestrator (supervisor), which classifies
  the intent and routes it to the correct agent. If a mall order is confirmed,
  the system automatically hands off to the Calculator to compute the total.

                        ┌─────────────┐
                        │    START    │
                        └──────┬──────┘
                               │
                        ┌──────▼──────┐
                        │ Orchestrator│  ← classifies & routes
                        └──────┬──────┘
               ┌───────────────┼───────────────┐
               │               │               │
        ┌──────▼──────┐ ┌──────▼──────┐ ┌──────▼──────┐
        │  Calculator │ │    Mall     │ │  Fallback   │
        │    Agent    │ │    Agent    │ │             │
        └──────┬──────┘ └──────┬──────┘ └──────┬──────┘
               │               │               │
               │        ┌──────▼──────┐        │
               │        │  Calculator │        │
               │        │  Subgraph   │        │
               │        │ (if order   │        │
               │        │ confirmed)  │        │
               │        └──────┬──────┘        │
               └───────────────┼───────────────┘
                        ┌──────▼──────┐
                        │     END     │
                        └─────────────┘
"""

import json
import logging
from typing import TypedDict, Literal, Annotated

from langchain_core.messages import BaseMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages

from config import AgentConfig
from ..agent.orchestrator import OrchestratorAgent
from ..core.logger import get_agent_logger

logger = get_agent_logger("orchestrator")


# =========================================================
# STATE DEFINITIONS
# =========================================================
# AgentState: shared state passed between all nodes in the main graph.
# CalculationState: isolated state used only inside the calculator subgraph.

class AgentState(TypedDict):
    query:      str       # The raw user input
    route_to:   str       # Which agent the orchestrator decided to use
    result:     dict      # The final output returned to the user
    error:      str       # Error message if something goes wrong
    history:    list      # Conversation history for multi-turn context
    last_agent: str       # Tracks which agent handled the previous turn


class CalculationState(TypedDict):
    items:       list[dict]                          # Line items from a confirmed order
    tax_rate:    float                               # Tax rate to apply (e.g. 0.09 = 9%)
    messages:    Annotated[list[BaseMessage], add_messages]
    calc_result: dict                                # Calculation output (subtotal, tax, total)


# =========================================================
# INITIALISATION
# =========================================================
# Load config and spin up the orchestrator, which holds the agent registry.

_config       = AgentConfig()
_orchestrator = OrchestratorAgent(_config)

# AGENTS is a dict like: { "calculator": <CalculatorAgent>, "mall": <MallAgent> }
AGENTS = _orchestrator.registry


# =========================================================
# CALCULATOR SUBGRAPH
# =========================================================
# This subgraph is invoked internally when a mall order is confirmed.
# It takes the confirmed line items and computes subtotal, tax, and grand total.

def _build_calculator_subgraph():

    def calc_entry(state: CalculationState) -> CalculationState:
        """
        Builds a natural-language prompt from the confirmed order items
        and sends it to the Calculator agent to compute the totals.
        """
        items    = state.get("items", [])
        tax_rate = state.get("tax_rate", 0.09)

        # Format each item as a readable line for the prompt
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

        result = AGENTS["calculator"].run(prompt)

        # Extract the last AI message as the calculation summary
        calc_result = {"status": "ok", "summary": ""}
        for msg in reversed(result.get("messages", [])):
            if type(msg).__name__ == "AIMessage" and msg.content:
                calc_result["summary"] = msg.content
                break

        return {**state, "messages": result.get("messages", []), "calc_result": calc_result}

    # Build a minimal single-node subgraph for the calculation step
    sub = StateGraph(CalculationState)
    sub.add_node("calc_entry", calc_entry)
    sub.add_edge(START, "calc_entry")
    sub.add_edge("calc_entry", END)
    return sub.compile()


# Compile once at module load — reused across all requests
_calculator_subgraph = _build_calculator_subgraph()


# =========================================================
# HELPERS
# =========================================================

def _extract_confirmed_items(result: dict) -> list[dict]:
    """
    Scans the mall agent's message history for a confirmed order.

    Returns a list of line items (name, price, currency, quantity)
    only when:
      - A ToolMessage with status="confirmed" is found, AND
      - The AI explicitly requested a total via [TOTAL_REQUESTED]

    Returns an empty list if no confirmed order is detected,
    or if price data is missing (prevents bad handoffs).
    """
    confirmed_data = None

    # Step 1: Find the most recent confirmed order in tool messages
    for msg in result.get("messages", []):
        if type(msg).__name__ != "ToolMessage":
            continue

        # Normalise content to a dict regardless of format
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

    # Step 2: Validate that price is present before proceeding
    price    = confirmed_data.get("price", 0.0)
    quantity = confirmed_data.get("quantity", 1)

    if not price:
        logger.warning(
            f"[_extract_confirmed_items] price missing from confirmed order — "
            f"handoff skipped. data: {confirmed_data}"
        )
        return []

    # Step 3: Only trigger calculator if the AI explicitly requested totals
    for msg in result.get("messages", []):
        if type(msg).__name__ == "AIMessage" and "[TOTAL_REQUESTED]" in (msg.content or ""):
            return [{
                "name":     confirmed_data.get("item", ""),
                "price":    price,
                "currency": confirmed_data.get("currency", "USD"),
                "quantity": quantity,
            }]

    return []


# Simple confirmation vocabulary — used to detect short replies like "yes", "ok", "cancel"
_CONFIRMATION_WORDS = {
    "yes", "ok", "confirm", "go ahead", "sure", "yep", "yeah", "proceed", "do it", "place it",
    "no", "cancel", "nope",
}


# =========================================================
# NODES
# =========================================================

def orchestrator_node(state: AgentState) -> AgentState:
    """
    Supervisor node — the entry point for every user query.

    Responsibilities:
      1. If the user sends a short confirmation word (e.g. "yes", "ok"),
         re-route to the same agent that handled the previous turn.
      2. Otherwise, classify the query and determine which agent to use.

    Sets `route_to` in state, which is read by `route_query` below.
    """
    query      = state["query"].strip().lower()
    last_agent = state.get("last_agent", "none")

    # Short-circuit: treat confirmation words as continuation of previous agent's task
    if query in _CONFIRMATION_WORDS and last_agent != "none":
        logger.info(f"[route] confirmation word detected | continuing with: {last_agent}")
        return {**state, "route_to": last_agent}

    # Full classification for all other queries
    route = _orchestrator.classify(query, last_agent=last_agent)
    logger.info(f"[route] query: '{query}' | last_agent: {last_agent} | routed to: {route}")
    return {**state, "route_to": route}


def calculator_node(state: AgentState) -> AgentState:
    """
    Runs the Calculator agent for direct math queries.
    Handles basic arithmetic and cost breakdowns.
    """
    try:
        result = AGENTS["calculator"].run(state["query"], state.get("history", []))
        return {**state, "result": result, "error": ""}

    except Exception as e:
        logger.error(f"[calculator_node] {e}")
        return {**state, "result": {}, "error": str(e)}


def mall_node(state: AgentState) -> AgentState:
    """
    Runs the Mall agent for shopping-related queries.
    Handles product search, store lookup, and order booking.

    Auto-handoff to Calculator:
      If the mall agent confirms an order and the AI requests a total,
      this node automatically invokes the calculator subgraph to
      compute subtotal, tax, and grand total — no extra user input needed.
    """
    try:
        result = AGENTS["mall"].run(state["query"], state.get("history", []))
        items  = _extract_confirmed_items(result)

        if items:
            # Log what's being handed off for traceability
            item_labels = [
                f"{i['quantity']}x {i['name']} @ {i['price']} {i['currency']}"
                for i in items
            ]
            logger.info(f"[handoff] mall → calculator | items: {item_labels}")

            # Invoke the calculator subgraph with the confirmed items
            tax_rate   = getattr(_config, "tax_rate", 0.09)
            calc_state = _calculator_subgraph.invoke({
                "items":       items,
                "tax_rate":    tax_rate,
                "messages":    [],
                "calc_result": {},
            })

            # Attach the calculation result to the mall result for the response
            result["calc_result"] = calc_state["calc_result"]
            logger.info(
                f"[handoff] calculator complete | "
                f"summary: {result['calc_result'].get('summary', '')[:80]}"
            )
        else:
            logger.debug("[handoff] no confirmed order — calculator not invoked")

        return {**state, "result": result, "error": ""}

    except Exception as e:
        logger.error(f"[mall_node] {e}")
        return {**state, "result": {}, "error": str(e)}


def fallback_node(state: AgentState) -> AgentState:
    """
    Catches any query that couldn't be routed to a known agent.
    Returns a helpful error listing the available agents.
    """
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

def route_query(state: AgentState) -> Literal["calculator", "mall", "fallback"]:
    """
    Conditional edge function — reads `route_to` from state
    and returns the name of the next node to execute.
    """
    return _orchestrator.route(state["route_to"])


# =========================================================
# GRAPH BUILDER
# =========================================================

def build_graph():
    """
    Assembles and compiles the full multi-agent graph.

    Nodes:
      - orchestrator : supervises and routes every query
      - calculator   : handles math queries
      - mall         : handles shopping queries (+ auto-handoff to calculator)
      - fallback     : handles unrecognised queries

    Edges:
      START → orchestrator → (conditional) → calculator | mall | fallback → END
    """
    graph = StateGraph(AgentState)

    # Register all nodes
    graph.add_node("orchestrator", orchestrator_node)
    graph.add_node("calculator",   calculator_node)
    graph.add_node("mall",         mall_node)
    graph.add_node("fallback",     fallback_node)

    # Entry point: always start at the orchestrator
    graph.add_edge(START, "orchestrator")

    # Supervisor routes to one of three agents based on query classification
    graph.add_conditional_edges(
        "orchestrator",
        route_query,
        {
            "calculator": "calculator",
            "mall":       "mall",
            "fallback":   "fallback",
        },
    )

    # All agents terminate after completing their task
    graph.add_edge("calculator", END)
    graph.add_edge("mall",       END)
    graph.add_edge("fallback",   END)

    return graph.compile()