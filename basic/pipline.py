from chroma_retriever import retrieve_chroma
# from faiss_retiever import retrieve
from generator import generate_answer

def rag_pipeline(query):
    print("Origin query: ", query)
    
    # Step 1: Retrieve
    retrieved_docs = retrieve_chroma(query)
    print("Retieved docs: ", retrieved_docs)
    
    # Step 2: Combine context
    context = "\n".join(retrieved_docs)
    print("Combined query: ", context)
    
    # Step 3: Generate answer
    answer = generate_answer(query, context)
    
    return answer