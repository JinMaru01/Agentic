documents = [
    # --- RAG Basics ---
    "Retrieval-Augmented Generation (RAG) is a technique that combines information retrieval with text generation.",
    "RAG improves LLM accuracy by grounding responses in external knowledge sources.",
    "A typical RAG pipeline includes embedding, retrieval, and generation stages.",
    "RAG helps reduce hallucination by providing relevant context to the language model.",

    # --- Agentic RAG ---
    "Agentic RAG extends RAG by allowing the system to plan, reason, and take actions autonomously.",
    "In Agentic RAG, multiple agents can collaborate to solve complex tasks step by step.",
    "A planner agent decides which tools or retrieval steps to use in Agentic RAG.",
    "Agentic systems can refine queries and perform multiple retrieval iterations.",

    # --- Embeddings ---
    "Embeddings transform text into dense vector representations for similarity comparison.",
    "Sentence Transformers are commonly used for generating embeddings in RAG systems.",
    "Similar texts have vectors that are close in embedding space.",
    "Embedding models like all-MiniLM-L6-v2 are efficient and widely used.",

    # --- Vector Databases ---
    "FAISS is a fast similarity search library developed by Facebook AI.",
    "Chroma is a lightweight vector database designed for AI applications.",
    "Vector databases store embeddings and enable fast nearest-neighbor search.",
    "Top-K retrieval returns the most similar documents to a query.",

    # --- LLMs ---
    "Large Language Models (LLMs) generate human-like text based on input prompts.",
    "LLMs use transformer architecture to understand and generate language.",
    "Context provided to LLMs directly influences the quality of generated answers.",
    "Smaller models like Phi can be used for local inference.",

    # --- Use Cases ---
    "RAG is widely used in chatbots, search engines, and question-answering systems.",
    "Companies use RAG for document search, customer support, and knowledge management.",
    "Resume analyzers can use RAG to match candidates with job descriptions.",
    "RAG is useful for enterprise data where up-to-date information is required.",

    # --- Limitations ---
    "RAG performance depends heavily on the quality of retrieved documents.",
    "Poor chunking strategies can reduce retrieval accuracy.",
    "Latency can increase due to retrieval and generation steps.",
    "Embedding mismatch can lead to irrelevant search results.",

    # --- Advanced Concepts ---
    "Hybrid search combines keyword-based and vector-based retrieval.",
    "Reranking models improve retrieval quality by reordering results.",
    "Chunking splits large documents into smaller pieces for better retrieval.",
    "Query rewriting improves search results by reformulating user questions."
]