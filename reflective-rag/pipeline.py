# from .generator import agentic_generate
from .response import generate_answer, generate_critique, refine_answer
from retriever.chroma import retrieve_chroma
from evaluator.ragas_eval import evaluate_rag_response

# def agentic_rag_pipeline(query):
#     context = retrieve_chroma(query)
#     return agentic_generate(query, context)

def agentic_rag_pipeline(query, ground_truth=None):

    retrieved = retrieve_chroma(query)
    contexts = [item["document"] for item in retrieved]
    distances = [item["distance"] for item in retrieved]

    if not contexts:
        response = ("Sorry, I don't have knowledge related to your question. please provide more detail of your question.")

        return {
            "query": query,
            "response": response,
            "contexts": [],
            "retrieval_scores": [],
            "critique": None,
            "evaluation": None
        }
    
    answer = generate_answer(query=query, context=contexts, mode="analysis")
    # print("\nGenerated answer:\n", answer)
    critique = generate_critique(query=query, context=contexts, answer=answer)
    # print("\nGenerated critique:\n", critique)
    final_answer = answer

    if "VALID" not in critique:
        final_answer = refine_answer(query=query, context=contexts, answer=answer, critique=critique)

    evaluation = None

    if ground_truth:
        evaluation = evaluate_rag_response(question=query, answer=final_answer, contexts=contexts, ground_truth=ground_truth)

    return {
        "query": query,
        "response": final_answer,
        "contexts": contexts,
        "retrieval_scores": distances,
        "initial_answer": answer,
        "critique": critique,
        "evaluation": evaluation
    }