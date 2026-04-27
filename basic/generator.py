import requests

LLM_URL = "http://ollama-server/api/generate"
MODEL = ["llama3.1:8b-instruct-"q3_K_L", "phi", "llama3.1:8b", deepseek-r1:7b", "qwen3:30b-instruct", "qwen3:4b-instruct"]


def generate_answer(query, context):
    prompt = f"""
You are an expert assistant.

Instructions:
- Use ONLY the provided context
- If answer is not in context, say "I don't know"
- Be concise and accurate

Context:
{context}

Question: {query}

Answer:
"""
    # print("Generated prompt: ", prompt)
    response = requests.post(
        LLM_URL,
        json={
            "model": MODEL[3],
            "prompt": prompt,
            "stream": False
        }
    )

    result = response.json()
    return result.get("response", "")