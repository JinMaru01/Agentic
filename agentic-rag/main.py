from .pipeline import agentic_rag_pipeline

print("=== Agentic RAG Terminal Chat ===")
print("Type 'exit' or 'quit' to stop\n")

while True:
    query = input("Enter your question: ").strip()
    
    if query.lower() in ["exit", "quit"]:
        print("Exiting...")
        break

    if not query:
        continue

    try:
        results = agentic_rag_pipeline(query)
        contexts = results["contexts"]
        response = results["response"]
        print("\nGenerated contexts:\n", contexts)
        print("\nGenerated response:\n", response)
        print("-" * 50)
    except Exception as e:
        print(f"Error: {e}")