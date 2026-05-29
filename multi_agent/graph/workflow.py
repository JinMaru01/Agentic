import json
from typing import TypedDict, Literal, Annotated

from langchain_core.messages import BaseMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages

from config import AgentConfig
from ..agent.orchestrator import OrchestratorAgent


# =========================================================
# STATE
# =========================================================

class AgentState(TypedDict):
    query:    str
    route_to: str
    result:   dict
    error:    str
    history:  list


class CalculationState(TypedDict):
    items:       list[dict]
    tax_rate:    float
    messages:    Annotated[list[BaseMessage], add_messages]
    calc_result: dict


# =========================================================
# ORCHESTRATOR
# =========================================================

_config       = AgentConfig()
_orchestrator = OrchestratorAgent(_config)

AGENTS = _orchestrator.registry


# =========================================================
# CALCULATOR SUBGRAPH
# =========================================================

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

        result = AGENTS["calculator"].run(prompt)

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


# instantiate once at module load
_calculator_subgraph = _build_calculator_subgraph()


# =========================================================
# HELPERS
# =========================================================

def _extract_confirmed_items(result: dict) -> list[dict]:

    for msg in result.get("messages", []):
        if type(msg).__name__ != "ToolMessage":
            continue

        content = msg.content

        # content can be a raw string, a JSON string, or already a list/dict
        if isinstance(content, list):
            # take the first element if it's a list of dicts
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

        # data itself might still be a list after parsing
        if isinstance(data, list):
            data = data[0] if data else {}

        if not isinstance(data, dict):
            continue

        if data.get("status") == "confirmed":
            return [{
                "name":     data.get("item", ""),
                "price":    data.get("price", 0.0),
                "currency": data.get("currency", "USD"),
                "quantity": 1,
            }]

    return []


# =========================================================
# NODES
# =========================================================

def orchestrator_node(state: AgentState) -> AgentState:

    route = _orchestrator.classify(state["query"])
    return {**state, "route_to": route}


# ---------------------------------------------------------

def calculator_node(state: AgentState) -> AgentState:

    try:
        result = AGENTS["calculator"].run(state["query"], state.get("history", []))
        return {**state, "result": result, "error": ""}

    except Exception as e:
        return {**state, "result": {}, "error": str(e)}


# ---------------------------------------------------------

def mall_node(state: AgentState) -> AgentState:

    try:
        result = AGENTS["mall"].run(state["query"], state.get("history", []))

        items = _extract_confirmed_items(result)

        if items:
            tax_rate   = getattr(_config, "tax_rate", 0.09)
            calc_state = _calculator_subgraph.invoke({
                "items":       items,
                "tax_rate":    tax_rate,
                "messages":    [],
                "calc_result": {},
            })
            result["calc_result"] = calc_state["calc_result"]

        return {**state, "result": result, "error": ""}

    except Exception as e:
        return {**state, "result": {}, "error": str(e)}


# ---------------------------------------------------------

def fallback_node(state: AgentState) -> AgentState:

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

    return _orchestrator.route(state["route_to"])


# =========================================================
# GRAPH BUILDER
# =========================================================

def build_graph():

    graph = StateGraph(AgentState)

    graph.add_node("orchestrator", orchestrator_node)
    graph.add_node("calculator",   calculator_node)
    graph.add_node("mall",         mall_node)
    graph.add_node("fallback",     fallback_node)

    graph.add_edge(START, "orchestrator")

    graph.add_conditional_edges(
        "orchestrator",
        route_query,
        {
            "calculator": "calculator",
            "mall":       "mall",
            "fallback":   "fallback",
        },
    )

    graph.add_edge("calculator", END)
    graph.add_edge("mall",       END)
    graph.add_edge("fallback",   END)

    return graph.compile()