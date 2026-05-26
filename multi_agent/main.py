from .graph.workflow import build_graph


# =========================================================
# DISPLAY HELPER
# =========================================================

def pretty_print(state: dict):
    """
    Renders the final graph state in a readable format.
    Delegates message formatting to CalculatorAgent when
    the result contains messages.
    """

    print(f"\n  Routed to : {state.get('route_to', 'N/A')}")

    # --- error path ---------------------------------------

    if state.get("error"):
        print(f"  Error     : {state['error']}")
        return

    # --- success path -------------------------------------

    result = state.get("result", {})

    if not result:
        print("  Result    : (empty)")
        return

    # Use the agent's own pretty_print for message traces
    if "messages" in result:
        from .graph.workflow import AGENTS
        agent = AGENTS.get(state["route_to"])
        if agent and hasattr(agent, "pretty_print"):
            agent.pretty_print(result)
        else:
            print(f"  Result    : {result}")
    else:
        print(f"  Result    : {result}")


# =========================================================
# MAIN
# =========================================================

def main():

    graph = build_graph()

    print("\nMulti-Agent System Ready")
    print("Type 'exit' to quit\n")

    while True:

        query = input("Enter your question: ").strip()

        if query.lower() in ["exit", "quit"]:
            print("\nExiting...")
            break

        if not query:
            continue

        # --- build initial state --------------------------

        initial_state = {
            "query":    query,
            "route_to": "",
            "result":   {},
            "error":    "",
        }

        # --- run graph ------------------------------------

        try:
            final_state = graph.invoke(initial_state)
            print("\n" + "=" * 60)
            pretty_print(final_state)
            print("=" * 60)

        except Exception as e:
            print(f"\nERROR: {e}")


# =========================================================
# ENTRY
# =========================================================

if __name__ == "__main__":
    main()