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


from typing import List, Dict, Any

from langchain_ollama import ChatOllama
from langchain.agents import create_agent

from config import AgentConfig
from ..prompts.calculator_prompts import SYSTEM_PROMPT
from ..tools.calculator_tools import (add, subtract, multiply, divide, power, sqrt,
                    nth_root, percentage, percent_change, safe_eval)



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
