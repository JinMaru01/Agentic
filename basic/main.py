from pipline import rag_pipeline

print("=== RAG Terminal Chat ===")
print("Type 'exit' or 'quit' to stop\n")

while True:
    query = input("Enter your question: ").strip()
    
    if query.lower() in ["exit", "quit"]:
        print("Exiting...")
        break

    if not query:
        continue

    try:
        response = rag_pipeline(query)
        print("\nGenerated response:\n", response)
        print("-" * 50)
    except Exception as e:
        print(f"Error: {e}")