import json

from langchain_ollama import ChatOllama

from config import AgentConfig
from ..prompts.orchestrator import ROUTER_PROMPT
from ..tools.orchestrator import build_registry, route_query


class OrchestratorAgent:

    def __init__(self, config: AgentConfig):

        self.config   = config
        self.registry = build_registry(config)
        self.llm      = self._build_llm()

    # -----------------------------------------------------

    def _build_llm(self):

        return ChatOllama(
            model=self.config.model_name,
            temperature=0,
            base_url=self.config.base_url,
        )

    # -----------------------------------------------------

    def classify(self, query: str, last_agent: str = "none") -> str:

        try:
            response = self.llm.invoke(
                ROUTER_PROMPT.format(query=query, last_agent=last_agent)
            )
            parsed = json.loads(response.content.strip())
            route  = parsed.get("agent", "search")

            if route not in self.registry:
                route = "search"  # any unrecognised route falls back to search

            return route

        except Exception:
            return "search"

    # -----------------------------------------------------

    def route(self, route_to: str) -> str:

        return route_query(route_to, self.registry)