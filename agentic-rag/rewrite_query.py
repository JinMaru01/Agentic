import requests
from load_env import MODEL_CONFIG, LLM_URL

def rewrite_query(query):

    prompt = f"""
Improve this search query for vector retrieval.

Original Query:
{query}

Return ONLY the improved query.
"""

    response = requests.post(
        LLM_URL,
        json={
            "model": MODEL_CONFIG["light"],
            "prompt": prompt,
            "stream": False
        }
    )

    return response.json()["response"].strip()