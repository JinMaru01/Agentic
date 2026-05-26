from config import AgentConfig
from .agent.calculator import CalculatorAgent

# =========================================================
# MAIN
# =========================================================

def main():

    config = AgentConfig()
    agent = CalculatorAgent(config)

    print("\nCalculator Agent Ready")
    print("Type 'exit' to quit\n")

    while True:

        query = input("Enter your question: ").strip()

        if query.lower() in ["exit", "quit"]:
            print("\nExiting...")
            break

        if not query:
            continue

        try:
            result = agent.run(query)
            print("\n" + "=" * 60)
            agent.pretty_print(result)
            print("\n" + "=" * 60)

        except Exception as e:
            print(f"\nERROR: {e}")


# =========================================================
# ENTRY
# =========================================================

if __name__ == "__main__":
    main()