import requests
from load_env import MODEL_CONFIG, LLM_URL

def select_model(mode="simple"):
    if mode == "analysis":
        return MODEL_CONFIG["default"]
    elif mode == "critique":
        return MODEL_CONFIG["light"]
    elif mode == "simple":
        return MODEL_CONFIG["fast"]
    return MODEL_CONFIG["default"]


def generate_answer(query, context, mode="simple"):
    context_text = "\n".join(context) if isinstance(context, list) else context

    prompt = f"""
You are an expert assistant.

Instructions:
- Use ONLY the provided context
- If answer is not in context, say "I don't know"
- Be concise and accurate

Context:
{context_text}

Question: {query}

Answer:
"""

    response = requests.post(
        LLM_URL,
        json={
            "model": select_model(mode),
            "prompt": prompt,
            "stream": False
        }
    )

    return response.json().get("response", "")


def generate_critique(query, context, answer):
    context_text = "\n".join(context)

    prompt = f"""
You are an expert evaluator.

Evaluate whether the answer is:
- factually supported by the context
- complete
- accurate
- free from hallucination

Context:
{context_text}

Question:
{query}

Answer:
{answer}

If issues exist, explain them clearly.
If answer is good, say: VALID
"""

    response = requests.post(
        LLM_URL,
        json={
            "model": MODEL_CONFIG["light"],
            "prompt": prompt,
            "stream": False
        }
    )

    return response.json()["response"]

def refine_answer(query, context, answer, critique):
    context_text = "\n".join(context)

    prompt = f"""
You are improving a RAG answer.

Original Context:
{context_text}

Question:
{query}

Original Answer:
{answer}

Critique:
{critique}

Generate an improved answer using ONLY the context.
"""

    response = requests.post(
        LLM_URL,
        json={
            "model": MODEL_CONFIG["default"],
            "prompt": prompt,
            "stream": False
        }
    )

    return response.json()["response"]