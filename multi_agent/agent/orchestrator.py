import json

from langchain_ollama import ChatOllama

from config import AgentConfig
from ..prompts.orchestrator import ROUTER_PROMPT
from ..tools.orchestrator import build_registry, route_query


# =========================================================
# ORCHESTRATOR AGENT
# =========================================================

class OrchestratorAgent:

    def __init__(self, config: AgentConfig):

        self.config = config
        self.registry = build_registry(config)
        self.llm = self._build_llm()

    # -----------------------------------------------------

    def _build_llm(self):

        return ChatOllama(
            model=self.config.model_name,
            temperature=0,              # deterministic routing
            base_url=self.config.base_url,
        )

    # -----------------------------------------------------

    def classify(self, query: str) -> str:
        """
        Calls the LLM to classify the query into an agent key.
        Returns 'unknown' on any parse failure.
        """

        try:
            response = self.llm.invoke(
                ROUTER_PROMPT.format(query=query)
            )
            parsed = json.loads(response.content.strip())
            route = parsed.get("agent", "unknown")

            if route not in self.registry:
                route = "unknown"

            return route

        except Exception:
            return "unknown"

    # -----------------------------------------------------

    def route(self, route_to: str) -> str:
        """Resolves route_to to the next graph node name."""

        return route_query(route_to, self.registry)