# =========================================================
# IMPORTS
# =========================================================

from typing import Dict, Any

from langchain_ollama import ChatOllama
from langgraph.prebuilt import create_react_agent

from config import AgentConfig
from ..prompts.mall_prompts import SYSTEM_PROMPT
from ..tools.mall_tool import tools
<<<<<<< HEAD

=======
from ..core.logger import get_agent_logger

logger = get_agent_logger("mall")
>>>>>>> 60b77f7c7c52089b682654bc96d87a8f65316ce3

# =========================================================
# MALL AGENT
# =========================================================

class MallAgent:

    def __init__(self, config: AgentConfig):

        self.config = config
        self.llm = self._build_llm()
        self.tools = self._build_tools()
        self.agent = self._build_agent()

<<<<<<< HEAD
=======
        logger.info("MallAgent initialized")

>>>>>>> 60b77f7c7c52089b682654bc96d87a8f65316ce3
    # -----------------------------------------------------

    def _build_llm(self):
        
        return ChatOllama(
            model=self.config.model_name,
            temperature=self.config.temperature,
            base_url=self.config.base_url,
        )

    # -----------------------------------------------------

    def _build_tools(self):

        return tools

    # -----------------------------------------------------

    def _build_agent(self):

        return create_react_agent(
            model=self.llm,
            tools=self.tools,
            prompt=SYSTEM_PROMPT,
        )

    # -----------------------------------------------------

<<<<<<< HEAD
    def run(self, query: str, history: list = []) -> Dict[str, Any]:

        return self.agent.invoke({
=======
    def run(self, query: str, history: list = []) -> dict:
        logger.info(f"[run] query: {query}")

        result = self.agent.invoke({
>>>>>>> 60b77f7c7c52089b682654bc96d87a8f65316ce3
            "messages": [
                *history,
                {"role": "user", "content": query}
            ]
        })
<<<<<<< HEAD
=======

        for msg in result.get("messages", []):
            msg_type = type(msg).__name__

            if msg_type == "AIMessage":
                if getattr(msg, "tool_calls", None):
                    for tc in msg.tool_calls:
                        logger.info(f"[tool_call] {tc['name']} | args: {tc['args']}")

            elif msg_type == "ToolMessage":
                logger.debug(f"[tool_result] {msg.content[:200]}")

            elif msg_type == "AIMessage" and msg.content:
                clean = msg.content.replace("[TOTAL_REQUESTED]", "").strip()
                if clean:
                    logger.info(f"[response] {clean[:200]}")

        logger.info(f"[run] complete")
        return result
>>>>>>> 60b77f7c7c52089b682654bc96d87a8f65316ce3
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