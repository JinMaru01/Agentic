import requests
from load_env import MODEL_CONFIG, LLM_URL

def select_model(mode="simple"):
    if mode == "analysis":
        return MODEL_CONFIG["strong"] or MODEL_CONFIG["default"]
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