import chromadb
from documents.documents import documents

client = chromadb.Client()
collection = client.create_collection("rag_demo")

collection.add(
    documents=documents,
    ids=[str(i) for i in range(len(documents))]
)

def retrieve_chroma(query, k=5, threshold=1):

    results = collection.query(
        query_texts=[query],
        n_results=k
    )

    documents = results["documents"][0]
    distances = results["distances"][0]

    filtered_docs = []

    for doc, distance in zip(documents, distances):

        if distance <= threshold:
            filtered_docs.append({
                "document": doc,
                "distance": distance
            })

    return filtered_docs