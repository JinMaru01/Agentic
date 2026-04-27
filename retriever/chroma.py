import chromadb
from documents.documents import documents

client = chromadb.Client()
collection = client.create_collection("rag_demo")

collection.add(
    documents=documents,
    ids=[str(i) for i in range(len(documents))]
)

def retrieve_chroma(query, k=2):
    results = collection.query(
        query_texts=[query],
        n_results=k
    )
    return results["documents"][0]