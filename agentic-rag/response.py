import requests

LLM_URL = "http://10.123.0.218:8080/api/generate"
MODEL = ["llama3.1:8b-instruct-q3_K_L", "phi", "llama3.1:8b", "deepseek-r1:7b", "qwen3:30b-instruct", "qwen3:4b-instruct"]


def generate_answer(query, context, mode="simple"):
    context_text = "\n".join(context) if isinstance(context, list) else context

    if mode == "simple":
        system_instruction = """
- Answer using ONLY the provided context
- If missing, say "I don't know"
- Keep it concise
"""

    elif mode == "analysis":
        system_instruction = """
- Use ONLY the provided context
- Think step-by-step before answering
- Provide a clear final answer
"""

    elif mode == "critique":
        system_instruction = """
- Evaluate if the answer is correct and complete
- Point out missing or incorrect parts
"""

    elif mode == "refine":
        system_instruction = """
- Improve the answer to be clearer and more complete
"""

    prompt = f"""
You are an expert assistant.

Instructions:
{system_instruction}

Context:
{context_text}

Question:
{query}

Answer:
"""

    response = requests.post(
        LLM_URL,
        json={
            "model": MODEL[3],
            "prompt": prompt,
            "stream": False
        }
    )

    return response.json().get("response", "")