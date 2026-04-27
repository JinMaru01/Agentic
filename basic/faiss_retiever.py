import numpy as np
from faiss import IndexFlatL2
from documents import documents
from embedding import embeddings, embedding_model


dimension = embeddings.shape[1]

index = IndexFlatL2(dimension)
index.add(np.array(embeddings))

def retrieve(query, k=2):
    query_vec = embedding_model.encode([query])
    distances, indices = index.search(query_vec, k)
    
    return [documents[i] for i in indices[0]]