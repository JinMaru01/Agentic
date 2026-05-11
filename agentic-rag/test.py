from .pipeline import agentic_rag_pipeline

result = agentic_rag_pipeline(
    query="What is Agentic RAG?",
    ground_truth="Agentic RAG combines retrieval with autonomous reasoning and planning."
)

print(result["response"])
print(result["evaluation"])