"""
Production-Style Calculator Agent
=================================

Architecture:
- Config
- Tools
- Prompt
- Agent Class
- CLI Runner

Compatible with:
- LangChain
- LangGraph
- Ollama

Authoring Style:
- Structured tools
- Safe evaluation
- Clean separation
- Reusable architecture
"""

# =========================================================
# IMPORTS
# =========================================================

import math
import ast
import operator as op
from dataclasses import dataclass
from typing import List, Dict, Any

from langchain_ollama import ChatOllama
from langchain.agents import create_agent
from langchain_core.tools import tool


# =========================================================
# CONFIG
# =========================================================

@dataclass
class AgentConfig:
    model_name: str = "qwen3:30b-instruct"
    base_url: str = "http://10.123.0.218:8080"
    temperature: float = 0


# =========================================================
# SYSTEM PROMPT
# =========================================================

SYSTEM_PROMPT = """ 
You are a precise calculator agent. 

Rules: 
- Always use tools for calculation 
- Never guess numbers 
- Break complex problems into steps 
- Prefer safe_eval for full expressions 
- Combine tools when necessary 
- Always show process to user step by step of calculation 
- Do your own calculation and compare with calculation use all tools 
- If result comparision not match ask user to check again on any tool 
"""


# =========================================================
# SAFE EVAL ENGINE
# =========================================================

SAFE_OPS = {
    ast.Add: op.add,
    ast.Sub: op.sub,
    ast.Mult: op.mul,
    ast.Div: op.truediv,
    ast.Pow: op.pow,
    ast.USub: op.neg,
}

SAFE_FUNCTIONS = {
    "sqrt": math.sqrt,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "log": math.log,
    "log10": math.log10,
}


# =========================================================
# TOOL DEFINITIONS
# =========================================================

@tool
def safe_eval(expr: str) -> float:
    """
    Safely evaluate mathematical expressions.

    Example:
    - (2+3)*5
    - sqrt(81)+10
    """

    def eval_node(node):

        # numbers
        if isinstance(node, ast.Constant):
            return node.value

        # binary operators
        if isinstance(node, ast.BinOp):
            return SAFE_OPS[type(node.op)](
                eval_node(node.left),
                eval_node(node.right),
            )

        # unary operators
        if isinstance(node, ast.UnaryOp):
            return SAFE_OPS[type(node.op)](
                eval_node(node.operand)
            )

        # function calls
        if isinstance(node, ast.Call):

            if not isinstance(node.func, ast.Name):
                raise ValueError("Invalid function call")

            func_name = node.func.id

            if func_name not in SAFE_FUNCTIONS:
                raise ValueError(
                    f"Function '{func_name}' is not allowed"
                )

            args = [eval_node(arg) for arg in node.args]

            return SAFE_FUNCTIONS[func_name](*args)

        raise ValueError(
            f"Unsupported operation: {type(node)}"
        )

    tree = ast.parse(expr, mode="eval")

    return eval_node(tree.body)


# ---------------------------------------------------------

@tool
def add(a: float, b: float) -> float:
    """Add two numbers."""
    return a + b


@tool
def subtract(a: float, b: float) -> float:
    """Subtract b from a."""
    return a - b


@tool
def multiply(a: float, b: float) -> float:
    """Multiply two numbers."""
    return a * b


@tool
def divide(a: float, b: float) -> float:
    """Divide a by b."""
    if b == 0:
        raise ValueError("Division by zero")
    return a / b


@tool
def power(a: float, b: float) -> float:
    """Compute a raised to power b."""
    return math.pow(a, b)


@tool
def sqrt(x: float) -> float:
    """Square root of a number."""
    return math.sqrt(x)


@tool
def nth_root(x: float, n: float) -> float:
    """Compute nth root of x."""
    return x ** (1 / n)


@tool
def percentage(value: float, percent: float) -> float:
    """Compute percentage of a value."""
    return (value * percent) / 100


@tool
def percent_change(old: float, new: float) -> float:
    """Calculate percentage change."""
    return ((new - old) / old) * 100


# =========================================================
# TOOL REGISTRY
# =========================================================

TOOLS = [
    add,
    subtract,
    multiply,
    divide,
    power,
    sqrt,
    nth_root,
    percentage,
    percent_change,
    safe_eval,
]


# =========================================================
# CALCULATOR AGENT
# =========================================================

class CalculatorAgent:

    def __init__(self, config: AgentConfig):

        self.config = config
        self.llm = self._build_llm()
        self.tools = self._build_tools()
        self.agent = self._build_agent()

    # -----------------------------------------------------

    def _build_llm(self):

        return ChatOllama(
            model=self.config.model_name,
            temperature=self.config.temperature,
            base_url=self.config.base_url,
        )

    # -----------------------------------------------------

    def _build_tools(self):

        return TOOLS

    # -----------------------------------------------------

    def _build_agent(self):

        return create_agent(
            model=self.llm,
            tools=self.tools,
            system_prompt=SYSTEM_PROMPT,
        )

    # -----------------------------------------------------

    def run(self, query: str) -> Dict[str, Any]:

        return self.agent.invoke({
            "messages": [
                {
                    "role": "user",
                    "content": query
                }
            ]
        })

    # -----------------------------------------------------

    def pretty_print(self, result: Dict[str, Any]):

        for msg in result["messages"]:
            msg_type = type(msg).__name__

            # ---------------------------------------------
            # USER
            # ---------------------------------------------

            if msg_type == "HumanMessage":
                print(f"\nUSER:")
                print(msg.content)

            # ---------------------------------------------
            # AI
            # ---------------------------------------------

            elif msg_type == "AIMessage":
                if msg.content:
                    print(f"\nAI:")
                    print(msg.content)

                if getattr(msg, "tool_calls", None):
                    for tool in msg.tool_calls:
                        print(
                            f"\nTOOL CALL:"
                            f"\n  Name : {tool['name']}"
                            f"\n  Args : {tool['args']}"
                        )

            # ---------------------------------------------
            # TOOL RESULT
            # ---------------------------------------------

            elif msg_type == "ToolMessage":

                print(f"\nTOOL RESULT:")
                print(msg.content)


# =========================================================
# MAIN
# =========================================================

def main():

    config = AgentConfig()
    agent = CalculatorAgent(config)

    print("\nCalculator Agent Ready")
    print("Type 'exit' to quit\n")

    while True:

        query = input("Enter your question: ").strip()

        if query.lower() in ["exit", "quit"]:
            print("\nExiting...")
            break

        if not query:
            continue

        try:
            result = agent.run(query)
            print("\n" + "=" * 60)
            agent.pretty_print(result)
            print("\n" + "=" * 60)

        except Exception as e:
            print(f"\nERROR: {e}")


# =========================================================
# ENTRY
# =========================================================

if __name__ == "__main__":
    main()