from langchain_ollama import ChatOllama
from langchain.agents import create_agent
from langchain_core.tools import tool
import math


# -----------------------------
# TOOL DEFINITIONS
# -----------------------------

@tool
def multiply_numbers(a: float, b: float) -> float:
    """Multiply two numbers."""
    return a * b



@tool
def square_root(value: float) -> float:
    """Square root of a number."""
    return math.sqrt(value)


tools = [multiply_numbers, square_root]

# -----------------------------
# LLM
# -----------------------------

llm = ChatOllama(
    model="qwen3:30b-instruct",
    temperature=0,
    base_url="http://10.123.0.218:8080"
)

# -----------------------------
# CREATE AGENT
# -----------------------------

agent = create_agent(
    model=llm,
    tools=tools,
    system_prompt="""
You are a calculator assistant.

Use:
- square_root for square roots
- multiply_numbers for multiplication
"""
)


# -----------------------------
# EXECUTOR
# -----------------------------

response = agent.invoke({
    "messages": [
        {
            "role": "user",
            "content": "What is the square root of 81 multiplied by 5?"
        }
    ]
})


# -----------------------------
# RUN
# -----------------------------

print("\nFINAL ANSWER:")
print(response)