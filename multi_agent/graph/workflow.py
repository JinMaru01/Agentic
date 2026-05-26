from typing import TypedDict, Literal

from langgraph.graph import StateGraph, START, END

from config import AgentConfig
from ..agent.calculator import CalculatorAgent


# =========================================================
# STATE
# =========================================================
# Shared state object that flows through every node in the
# graph. Each node reads from it and writes back to it.
# =========================================================

class AgentState(TypedDict):
    query: str                  # original user input
    route_to: str               # which agent the orchestrator picked
    result: dict                # raw output from the active agent
    error: str                  # error message if something failed


# =========================================================
# AGENT REGISTRY
# =========================================================
# Instantiate agents once at module load — not inside nodes.
# This avoids rebuilding the LLM connection on every call.
# Add new agents here as you build them.
# =========================================================

_config = AgentConfig()

AGENTS = {
    "calculator": CalculatorAgent(_config),
    # "pipeline_watch": PipelineWatchAgent(_config),   # ← next agent goes here
    # "data_quality":  DataQualityAgent(_config),      # ← and so on
}


# =========================================================
# NODES
# =========================================================


def orchestrator_node(state: AgentState) -> AgentState:
    """
    Decides which agent should handle the query.

    Right now: keyword-based routing (fast, deterministic).
    Later:      swap in an LLM call here for natural language
                routing across many agents.
    """

    query = state["query"].lower()

    # --- routing rules (extend as you add agents) ---------

    math_keywords = [
        "calculate", "compute", "add", "subtract", "multiply",
        "divide", "sqrt", "power", "percent", "+", "-", "*", "/",
        "root", "square", "formula", "math", "number",
    ]

    if any(kw in query for kw in math_keywords):
        route = "calculator"
    else:
        route = "unknown"

    return {**state, "route_to": route}


# ---------------------------------------------------------

def calculator_node(state: AgentState) -> AgentState:
    """Runs the calculator agent and stores the result."""

    try:
        result = AGENTS["calculator"].run(state["query"])
        return {**state, "result": result, "error": ""}

    except Exception as e:
        return {**state, "result": {}, "error": str(e)}


# ---------------------------------------------------------

def fallback_node(state: AgentState) -> AgentState:
    """
    Handles queries that didn't match any agent.
    Placeholder until more agents are added.
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

def route_query(state: AgentState) -> Literal["calculator", "fallback"]:
    """
    Called after orchestrator_node. Returns the name of the
    next node to execute based on state["route_to"].
    """

    routing_map = {
        "calculator": "calculator",
        # "pipeline_watch": "pipeline_watch",   # ← add when ready
        # "data_quality":   "data_quality",     # ← add when ready
    }

    return routing_map.get(state["route_to"], "fallback")


# =========================================================
# GRAPH BUILDER
# =========================================================

def build_graph():
    """
    Wires all nodes into a compiled LangGraph.

    Flow:
        START
          └─► orchestrator        (decides route)
                ├─► calculator    (math queries)
                └─► fallback      (unrecognised queries)
                        └─► END
    """

    graph = StateGraph(AgentState)

    # --- register nodes -----------------------------------

    graph.add_node("orchestrator", orchestrator_node)
    graph.add_node("calculator",   calculator_node)
    graph.add_node("fallback",     fallback_node)

    # --- define edges -------------------------------------

    graph.add_edge(START, "orchestrator")

    graph.add_conditional_edges(
        "orchestrator",
        route_query,
        {
            "calculator": "calculator",
            "fallback":   "fallback",
        },
    )

    graph.add_edge("calculator", END)
    graph.add_edge("fallback",   END)

    return graph.compile()