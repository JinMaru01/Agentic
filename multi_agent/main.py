from collections import defaultdict

from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

from .graph.workflow import build_graph, AGENTS, orchestrator_node, route_query


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

    # --- calculator handoff summary -----------------------
    calc = result.get("calc_result", {})
    if calc and calc.get("summary"):
        print(f"\nORDER TOTAL (via calculator agent):")
        print(calc["summary"])


# =========================================================
# HISTORY HELPERS
# =========================================================

def _append_turn(history: list, query: str, result: dict) -> list:

    history.append(HumanMessage(content=query))

    for msg in result.get("messages", []):
        if isinstance(msg, (AIMessage, ToolMessage)):
            history.append(msg)

    return history


# =========================================================
# MAIN
# =========================================================

def main():

    graph      = build_graph()
    histories  = defaultdict(list)
    last_agent = "none"

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

            probe_state = {
                "query":      query,
                "route_to":   "",
                "result":     {},
                "error":      "",
                "history":    [],
                "last_agent": last_agent,
            }

            routed_state = orchestrator_node(probe_state)
            agent_key    = route_query(routed_state)

            # --- pick the right history for this agent -----------

            agent_history = histories[agent_key]

            # --- run full graph with correct history + last_agent -

            initial_state = {
                "query":      query,
                "route_to":   "",
                "result":     {},
                "error":      "",
                "history":    agent_history,
                "last_agent": last_agent,
            }

            final_state = graph.invoke(initial_state)

            print("\n" + "=" * 60)
            pretty_print(final_state)
            print("=" * 60)

            # --- update history + last_agent on success ----------

            if not final_state.get("error") and final_state.get("result"):
                routed_key = final_state.get("route_to", agent_key)

                if routed_key not in ("unknown", "fallback", ""):
                    histories[routed_key] = _append_turn(
                        histories[routed_key],
                        query,
                        final_state["result"],
                    )
                    last_agent = routed_key

        except Exception as e:
            print(f"\nERROR: {e}")


# =========================================================
# ENTRY
# =========================================================

if __name__ == "__main__":
    main()