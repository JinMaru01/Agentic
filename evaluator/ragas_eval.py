from datasets import Dataset

from ragas import evaluate
from ragas.metrics import (
    faithfulness,
    answer_relevancy,
    context_precision,
    context_recall
)

from langchain_ollama import (
    ChatOllama,
    OllamaEmbeddings
)

from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import LangchainEmbeddingsWrapper

judge_llm = ChatOllama(
    model="qwen3:30b-instruct",
    temperature=0
)

embedding_model = OllamaEmbeddings(
    model="nomic-embed-text"
)

ragas_llm = LangchainLLMWrapper(judge_llm)

ragas_embeddings = LangchainEmbeddingsWrapper(
    embedding_model
)

def evaluate_rag_response(
    question,
    answer,
    contexts,
    ground_truth
):
    dataset = Dataset.from_dict({
        "question": [question],
        "answer": [answer],
        "contexts": [contexts],
        "ground_truth": [ground_truth]
    })

    result = evaluate(
        dataset=dataset,
        metrics=[
            faithfulness,
            answer_relevancy,
            context_precision,
            context_recall
        ],
        llm=ragas_llm,
        embeddings=ragas_embeddings
    )

    return result