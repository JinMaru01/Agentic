from .generator import agentic_generate
from retriever.chroma import retrieve_chroma

def agentic_rag_pipeline(query):
    context = retrieve_chroma(query)
    return agentic_generate(query, context)