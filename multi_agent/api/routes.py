import asyncio
import json
import logging
from typing import List

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

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
from ..graph.workflow import AGENTS, build_graph, orchestrator_node, route_query

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")

# Build the LangGraph graph once at import time
_graph = build_graph()

_AGENT_NODES = {"calculator", "mall", "browser", "search"}


# =========================================================
# HELPERS
# =========================================================

def _is_raw_json(text: str) -> bool:
    stripped = text.strip()
    if not stripped.startswith(('{', '[')):
        return False
    try:
        json.loads(stripped)
        return True
    except (json.JSONDecodeError, ValueError):
        return False


def _extract_response(result: dict, error: str) -> str:
    """
    Mirror main.py's pretty_print logic: collect every non-empty AI text,
    prefer the last clean (non-JSON) one, and fall back to the last AI text
    of any kind rather than a generic error message.
    """
    if error:
        return f"Sorry, I ran into an error: {error}"

    if not result:
        return "I couldn't process your request. Please try again."

    messages = result.get("messages", [])

    clean_texts: list[str] = []
    last_ai_text: str = ""

    for msg in messages:
        if type(msg).__name__ != "AIMessage":
            continue
        text = (msg.content or "").replace("[TOTAL_REQUESTED]", "").strip()
        if not text:
            continue
        last_ai_text = text
        if not _is_raw_json(text):
            clean_texts.append(text)

    content = clean_texts[-1] if clean_texts else last_ai_text

    if not content:
        return "I couldn't process your request. Please try again."

    calc = result.get("calc_result", {})
    if calc and calc.get("summary"):
        content += f"\n\n**Order Total:**\n{calc['summary']}"

    return content


def _build_probe_state(query: str, forced_agent: str, last_agent: str) -> dict:
    """Minimal state for the orchestrator probe — matches main.py's pattern."""
    return {
        "query":              query,
        "route_to":           "",
        "forced_agent":       forced_agent,
        "orchestrator_route": "",
        "suggested_agent":    "",
        "result":             {},
        "error":              "",
        "history":            [],
        "last_agent":         last_agent,
    }


def _build_initial_state(query: str, forced_agent: str, history: list, last_agent: str) -> dict:
    return {
        "query":              query,
        "route_to":           "",
        "forced_agent":       forced_agent,
        "orchestrator_route": "",
        "suggested_agent":    "",
        "result":             {},
        "error":              "",
        "history":            history,
        "last_agent":         last_agent,
    }


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
# CHAT  (sync — same control flow as main.py)
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

    forced_agent = "" if selected_agent == "auto" else selected_agent

    if forced_agent and forced_agent not in AGENTS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown agent '{forced_agent}'. Available: {list(AGENTS.keys())}",
        )

    session.add_display_message("user", query)

    try:
        # ── probe: determine routing + pick correct history bucket ──
        probe_state  = _build_probe_state(query, forced_agent, session.last_agent)
        routed_state = orchestrator_node(probe_state)
        # Use route_query exactly like main.py does
        agent_key    = route_query(routed_state) or forced_agent or "fallback"

        # ── full graph run with real conversation history ──
        initial_state = _build_initial_state(
            query, forced_agent,
            session.get_history(agent_key),
            session.last_agent,
        )
        final_state = _graph.invoke(initial_state)

        agent_used      = final_state.get("route_to", agent_key)
        suggested_agent = final_state.get("suggested_agent", "")
        error           = final_state.get("error", "")
        result          = final_state.get("result", {})

        response_text = _extract_response(result, error)

        suggestion_reason = (
            get_suggestion_reason(forced_agent or "auto", suggested_agent)
            if suggested_agent else None
        )

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
# STREAMING CHAT
# =========================================================

@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    session = session_store.get(request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found. Create one first.")

    query          = request.message.strip()
    selected_agent = request.selected_agent.lower()

    if not query:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    forced_agent = "" if selected_agent == "auto" else selected_agent

    if forced_agent and forced_agent not in AGENTS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown agent '{forced_agent}'. Available: {list(AGENTS.keys())}",
        )

    session.add_display_message("user", query)

    # Probe runs in a thread so it doesn't block the event loop
    probe_state  = _build_probe_state(query, forced_agent, session.last_agent)
    routed_state = await asyncio.to_thread(orchestrator_node, probe_state)
    agent_key    = route_query(routed_state) or forced_agent or "fallback"

    initial_state = _build_initial_state(
        query, forced_agent,
        session.get_history(agent_key),
        session.last_agent,
    )

    async def generate():
        collected: list[str] = []
        final_state: dict    = {}
        total_requested      = False

        try:
            async for event in _graph.astream_events(initial_state, version="v2"):
                kind = event.get("event", "")
                node = event.get("metadata", {}).get("langgraph_node", "")

                if kind == "on_chat_model_stream" and node in _AGENT_NODES:
                    chunk         = event["data"]["chunk"]
                    text          = chunk.content if hasattr(chunk, "content") else ""
                    has_tool_call = bool(getattr(chunk, "tool_call_chunks", None))

                    if text and not has_tool_call:
                        if "[TOTAL_REQUESTED]" in text:
                            total_requested = True
                            text = text.replace("[TOTAL_REQUESTED]", "")
                        collected.append(text)
                        if text:
                            yield f"data: {json.dumps({'token': text})}\n\n"

                elif kind == "on_chain_end" and event.get("name") == "LangGraph":
                    output = event.get("data", {}).get("output", {})
                    if isinstance(output, dict):
                        final_state = output

            result = final_state.get("result", {})
            error  = final_state.get("error", "")

            full_streamed = "".join(collected).strip()

            if not full_streamed:
                # Nothing was streamed — use the same extraction as the sync endpoint
                full_response = _extract_response(result, error)
                yield f"data: {json.dumps({'token': full_response})}\n\n"

            elif _is_raw_json(full_streamed):
                # Streamed content was raw JSON — replace it with the clean extraction
                logger.warning("[stream] streamed content is raw JSON — replacing")
                full_response = _extract_response(result, error)
                yield f"data: {json.dumps({'replace': full_response})}\n\n"

            else:
                full_response = full_streamed

                # Append calculator summary for confirmed mall orders
                calc = result.get("calc_result", {})
                if total_requested and calc and calc.get("summary"):
                    summary = f"\n\n**Order Total:**\n{calc['summary']}"
                    full_response += summary
                    yield f"data: {json.dumps({'token': summary})}\n\n"

            agent_used      = final_state.get("route_to", agent_key)
            suggested_agent = final_state.get("suggested_agent", "")

            suggestion_reason = (
                get_suggestion_reason(forced_agent or "auto", suggested_agent)
                if suggested_agent else None
            )

            if not error and result and agent_used not in ("unknown", "fallback", ""):
                session.update_history(agent_used, query, result)

            session.add_display_message("assistant", full_response, agent_used=agent_used)

            yield f"data: {json.dumps({'done': True, 'agent_used': agent_used, 'suggested_agent': suggested_agent or None, 'suggestion_reason': suggestion_reason})}\n\n"

        except Exception as exc:
            logger.exception("Error in /api/chat/stream")
            err_msg = f"Sorry, I ran into an error: {exc}"
            session.add_display_message("assistant", err_msg, agent_used="error")
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
