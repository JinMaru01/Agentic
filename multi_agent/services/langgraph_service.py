from collections import defaultdict

from langchain_core.messages import (
    HumanMessage,
    AIMessage,
    ToolMessage,
)

from ..graph.workflow import (
    build_graph,
    orchestrator_node,
    route_query,
)


class AgentService:

    def __init__(self):

        self.graph = build_graph()
        self.histories = defaultdict(list)
        self.last_agent_by_session = defaultdict(lambda: "none")

    def _append_turn(self, history, query, result):

        history.append(HumanMessage(content=query))
        for msg in result.get("messages", []):
            if isinstance(msg, (AIMessage, ToolMessage)):
                history.append(msg)

        return history

    def chat(self, query: str, session_id: str = "default"):

        last_agent = self.last_agent_by_session[session_id]

        probe_state = {
            "query": query,
            "route_to": "",
            "result": {},
            "error": "",
            "history": [],
            "last_agent": last_agent,
        }

        routed_state = orchestrator_node(probe_state)
        agent_key = route_query(routed_state)
        history = self.histories[agent_key]

        initial_state = {
            "query": query,
            "route_to": "",
            "result": {},
            "error": "",
            "history": history,
            "last_agent": last_agent,
        }

        final_state = self.graph.invoke(initial_state)

        if not final_state.get("error") and final_state.get("result"):
            routed_key = final_state.get("route_to", agent_key)

            self.histories[routed_key] = self._append_turn(
                self.histories[routed_key],
                query,
                final_state["result"],
            )

            self.last_agent_by_session[session_id] = routed_key

        return final_state