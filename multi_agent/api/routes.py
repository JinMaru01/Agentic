import logging
from typing import List

from fastapi import APIRouter, HTTPException

from .agent_info import AGENT_METADATA, get_suggestion_reason
from .schemas import (
    AgentInfo,
    ChatMessage,
    ChatRequest,
    ChatResponse,
    CreateSessionResponse,
    HistoryResponse,
    SessionInfo,
)
from .session import session_store
from ..graph.workflow import AGENTS, build_graph, orchestrator_node

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")

# Build the LangGraph graph once at import time (heavy — models load here)
_graph = build_graph()


# =========================================================
# AGENTS
# =========================================================

@router.get("/agents", response_model=List[AgentInfo])
async def list_agents():
    return list(AGENT_METADATA.values())


# =========================================================
# SESSIONS
# =========================================================

@router.post("/sessions", response_model=CreateSessionResponse)
async def create_session():
    session = session_store.create()
    return {"session_id": session.session_id}


@router.get("/sessions", response_model=List[SessionInfo])
async def list_sessions():
    return session_store.list_all()


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    if not session_store.delete(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "deleted"}


@router.get("/sessions/{session_id}/history", response_model=HistoryResponse)
async def get_history(session_id: str):
    session = session_store.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    messages = [ChatMessage(**m) for m in session.messages]
    return HistoryResponse(session_id=session_id, messages=messages)


# =========================================================
# CHAT
# =========================================================

@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    session = session_store.get(request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found. Create one first.")

    query          = request.message.strip()
    selected_agent = request.selected_agent.lower()

    if not query:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    # Map "auto" → no forced agent
    forced_agent = "" if selected_agent == "auto" else selected_agent

    if forced_agent and forced_agent not in AGENTS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown agent '{forced_agent}'. Available: {list(AGENTS.keys())}",
        )

    session.add_display_message("user", query)

    try:
        # Probe orchestrator to determine best agent (and detect mismatches)
        probe_state = {
            "query":              query,
            "route_to":           "",
            "forced_agent":       forced_agent,
            "orchestrator_route": "",
            "suggested_agent":    "",
            "result":             {},
            "error":              "",
            "history":            [],
            "last_agent":         session.last_agent,
        }
        routed_state = orchestrator_node(probe_state)
        agent_key    = routed_state["route_to"] or forced_agent or "fallback"

        # Run full graph with per-agent conversation history
        initial_state = {
            "query":              query,
            "route_to":           "",
            "forced_agent":       forced_agent,
            "orchestrator_route": "",
            "suggested_agent":    "",
            "result":             {},
            "error":              "",
            "history":            session.get_history(agent_key),
            "last_agent":         session.last_agent,
        }

        final_state = _graph.invoke(initial_state)

        agent_used      = final_state.get("route_to", agent_key)
        suggested_agent = final_state.get("suggested_agent", "")
        error           = final_state.get("error", "")
        result          = final_state.get("result", {})

        response_text = _extract_response(result, error)

        suggestion_reason = (
            get_suggestion_reason(forced_agent or "auto", suggested_agent)
            if suggested_agent
            else None
        )

        # Persist history on success
        if not error and result and agent_used not in ("unknown", "fallback", ""):
            session.update_history(agent_used, query, result)

        session.add_display_message("assistant", response_text, agent_used=agent_used)

        return ChatResponse(
            session_id        = request.session_id,
            response          = response_text,
            agent_used        = agent_used,
            suggested_agent   = suggested_agent or None,
            suggestion_reason = suggestion_reason,
            error             = error or None,
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Unhandled error in /api/chat")
        msg = str(exc)
        session.add_display_message("assistant", f"Error: {msg}", agent_used="error")
        raise HTTPException(status_code=500, detail=msg)


# =========================================================
# HELPERS
# =========================================================

def _extract_response(result: dict, error: str) -> str:
    if error:
        return f"Sorry, I ran into an error: {error}"

    if not result:
        return "I couldn't process your request. Please try again."

    messages = result.get("messages", [])
    for msg in reversed(messages):
        if type(msg).__name__ == "AIMessage" and msg.content:
            content = msg.content.replace("[TOTAL_REQUESTED]", "").strip()

            calc = result.get("calc_result", {})
            if calc and calc.get("summary"):
                content += f"\n\n**Order Total:**\n{calc['summary']}"

            return content

    return "Request processed."
