from collections import defaultdict
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from .graph.workflow import build_graph, AGENTS


# =========================================================
# DISPLAY HELPER
# =========================================================

def pretty_print(state: dict):

    print(f"\n  Routed to : {state.get('route_to', 'N/A')}")

    if state.get("error"):
        print(f"  Error     : {state['error']}")
        return

    result = state.get("result", {})

    if not result:
        print("  Result    : (empty)")
        return

    if "messages" in result:
        agent = AGENTS.get(state["route_to"])
        if agent and hasattr(agent, "pretty_print"):
            agent.pretty_print(result)
        else:
            print(f"  Result    : {result}")
    else:
        print(f"  Result    : {result}")


# =========================================================
# HISTORY HELPERS
# =========================================================

def _append_turn(history: list, query: str, result: dict) -> list:
    """
    Appends the latest user query and agent responses into
    the agent-specific history list.
    """

    history.append(HumanMessage(content=query))

    for msg in result.get("messages", []):
        if isinstance(msg, (AIMessage, ToolMessage)):
            history.append(msg)

    return history


def _build_state(query: str, history: list) -> dict:

    return {
        "query":    query,
        "route_to": "",
        "result":   {},
        "error":    "",
        "history":  history,
    }


# =========================================================
# MAIN
# =========================================================

def main():

    graph = build_graph()

    # Per-agent history — keyed by agent name, isolated per agent
    histories: dict[str, list] = defaultdict(list)

    print("\nMulti-Agent System Ready")
    print("Type 'exit' to quit\n")

    while True:

        query = input("Enter your question: ").strip()

        if query.lower() in ["exit", "quit"]:
            print("\nExiting...")
            break

        if not query:
            continue

        try:
            # --- first pass: orchestrate only to get route ----

            probe_state = {
                "query":    query,
                "route_to": "",
                "result":   {},
                "error":    "",
                "history":  [],
            }

            from .graph.workflow import orchestrator_node, route_query
            routed = orchestrator_node(probe_state)
            agent_key = route_query(routed)

            # --- pick the right history for this agent --------

            agent_history = histories[agent_key]

            # --- run full graph with correct history ----------

            initial_state = _build_state(query, agent_history)
            final_state = graph.invoke(initial_state)

            print("\n" + "=" * 60)
            pretty_print(final_state)
            print("=" * 60)

            # --- update only this agent's history -------------

            if not final_state.get("error") and final_state.get("result"):
                histories[agent_key] = _append_turn(
                    agent_history,
                    query,
                    final_state["result"],
                )

        except Exception as e:
            print(f"\nERROR: {e}")


# =========================================================
# ENTRY
# =========================================================

if __name__ == "__main__":
    main()