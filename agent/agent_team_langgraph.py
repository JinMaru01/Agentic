#!/usr/bin/env python3
"""
Agent Team Server — LangGraph Edition
======================================
Orchestrates .claude/agents/*.md definitions using LangGraph StateGraph +
LangChain tools + ChatOllama. Each agent runs a proper ReAct loop.
Team mode uses a Supervisor → Router → Agent subgraph pattern.

Install:
    pip install fastapi uvicorn httpx \
                langchain langchain-core langchain-ollama \
                langgraph

Run:
    python agent_team_langgraph.py
    python agent_team_langgraph.py --workspace d:/development/wingbank-ade --model qwen3:30b
"""

import argparse
import asyncio
import json
import logging
import operator
import os
import re
import subprocess
from pathlib import Path
from typing import Annotated, Any, TypedDict

# ── LangChain / LangGraph ──────────────────────────────────────────────────
from langchain_core.messages import (
    AIMessage, HumanMessage, SystemMessage, ToolMessage, BaseMessage
)
from langchain_core.tools import tool
from langchain_ollama import ChatOllama
from langgraph.prebuilt import create_react_agent
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.graph.message import add_messages

# ── FastAPI ────────────────────────────────────────────────────────────────
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import httpx

# ══════════════════════════════════════════════════════════════════════════
# LOGGING
# ══════════════════════════════════════════════════════════════════════════
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("agent-lg")

# ══════════════════════════════════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════════════════════════════════
CFG: dict[str, Any] = {
    "ollama_host":  os.getenv("OLLAMA_HOST",  "http://10.123.0.218:8080"),
    "model":        os.getenv("AGENT_MODEL",  "qwen3:30b-instruct"),
    "workspace":    os.getenv("WORKSPACE",    ".agent-app"),
    "agents_dir":   os.getenv("AGENTS_DIR",   ".claude/agents"),
    "strip_think":    True,
    "max_iterations": 25,
    "tool_timeout":   60,
    "read_max_lines": 300,
}

# Appended to every agent's system prompt — forces file creation via tool.
FILE_CREATION_RULES = """

---
## File Output Rules (MANDATORY)
When producing any new code, tests, migrations, configs, or documentation:
1. Call `CreateFile` to write it to disk — NEVER output code only in text.
2. `Write`  → full overwrite of an existing file
3. `Edit`   → targeted replacement inside an existing file
4. `CreateFile` → brand-new file that does not exist yet
After writing, verify with `Bash` (e.g. `python -m py_compile path/to/file.py`).
"""

# ══════════════════════════════════════════════════════════════════════════
# SESSION STATE  (reset per request)
# ══════════════════════════════════════════════════════════════════════════
_session: dict[str, Any] = {
    "artifacts": [],   # list of {path, content, lang, lines, description, agent}
    "file_log":  [],   # list of {action, path}
    "todos":     [],
}

def _reset_session() -> None:
    _session["artifacts"].clear()
    _session["file_log"].clear()
    _session["todos"].clear()

# ══════════════════════════════════════════════════════════════════════════
# WORKSPACE HELPERS
# ══════════════════════════════════════════════════════════════════════════
def _ws(relative: str) -> Path:
    """Resolve path inside workspace; raises if outside."""
    ws = Path(CFG["workspace"]).resolve()
    t  = (ws / relative.lstrip("/\\")).resolve()
    t.relative_to(ws)   # ValueError → outside workspace
    return t

def _lang(path: str) -> str:
    return {
        ".py":"python", ".ts":"typescript", ".tsx":"typescript",
        ".js":"javascript", ".jsx":"javascript", ".sql":"sql",
        ".yaml":"yaml", ".yml":"yaml", ".json":"json",
        ".md":"markdown", ".sh":"bash", ".toml":"toml",
        ".html":"html", ".css":"css",
    }.get(Path(path).suffix.lower(), "text")

def _strip_think(text: str) -> str:
    if CFG["strip_think"] and text:
        text = re.sub(r"<think>[\s\S]*?</think>", "", text, flags=re.IGNORECASE)
    return text.strip()

# ══════════════════════════════════════════════════════════════════════════
# LANGCHAIN TOOLS
# ══════════════════════════════════════════════════════════════════════════

@tool
def Read(path: str) -> str:
    """Read the contents of an existing file in the workspace."""
    try:
        p = _ws(path)
        if not p.exists():
            return f"[Error] Not found: {path}"
        text  = p.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        _session["file_log"].append({"action": "read", "path": path})
        if len(lines) > CFG["read_max_lines"]:
            return "\n".join(lines[:CFG["read_max_lines"]]) + f"\n\n[... {len(lines)-CFG['read_max_lines']} more lines. Use Bash+sed/grep for targeted reading.]"
        return text
    except PermissionError as e:
        return f"[PermissionError] {e}"
    except Exception as e:
        return f"[Error] {e}"


@tool
def CreateFile(path: str, content: str, description: str = "") -> str:
    """Create a brand-new file with generated code, tests, migrations, configs, or docs.
    ALWAYS use this for new files — never just show code in text.
    Returns an error if the file already exists (use Write to overwrite)."""
    try:
        p = _ws(path)
        if p.exists():
            return f"[Warning] File already exists: {path}. Use Write to overwrite, or Edit for targeted changes."
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        lines = len(content.splitlines())
        entry = {
            "path":        path,
            "content":     content,
            "lang":        _lang(path),
            "lines":       lines,
            "description": description,
        }
        _session["artifacts"].append(entry)
        _session["file_log"].append({"action": "create", "path": path})
        log.info(f"CreateFile: {path} ({lines} lines)")
        return f"[OK] Created {path} — {lines} lines"
    except PermissionError as e:
        return f"[PermissionError] {e}"
    except Exception as e:
        return f"[Error] {e}"


@tool
def Write(path: str, content: str) -> str:
    """Overwrite an existing file entirely with new content. Also creates the file if it doesn't exist."""
    try:
        p = _ws(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        existed = p.exists()
        p.write_text(content, encoding="utf-8")
        _session["file_log"].append({"action": "write", "path": path})
        return f"[OK] {'Overwrote' if existed else 'Created'} {path} — {len(content.splitlines())} lines"
    except Exception as e:
        return f"[Error] {e}"


@tool
def Edit(path: str, old_str: str, new_str: str) -> str:
    """Edit a file by replacing the first exact occurrence of old_str with new_str."""
    try:
        p = _ws(path)
        if not p.exists():
            return f"[Error] Not found: {path}"
        src = p.read_text(encoding="utf-8")
        if old_str not in src:
            idx  = src.lower().find(old_str[:30].lower())
            hint = f"\n  Near char {idx}: ...{src[max(0,idx-40):idx+80]}..." if idx >= 0 else ""
            return f"[Error] old_str not found in {path}.{hint}"
        p.write_text(src.replace(old_str, new_str, 1), encoding="utf-8")
        _session["file_log"].append({"action": "edit", "path": path})
        return f"[OK] Edited {path}"
    except Exception as e:
        return f"[Error] {e}"


@tool
def Bash(command: str) -> str:
    """Run a shell command in the workspace directory (cwd = workspace root). Use for pytest, pnpm, git, syntax checks, etc."""
    try:
        r = subprocess.run(
            command, shell=True, capture_output=True, text=True,
            cwd=CFG["workspace"], timeout=CFG["tool_timeout"],
            encoding="utf-8", errors="replace",
        )
        out = ((r.stdout or "") + ("\n[stderr]\n" + r.stderr if r.stderr else "")).strip()
        if r.returncode != 0:
            out = f"[exit {r.returncode}]\n{out}"
        return (out[:4000] + "\n[... truncated]") if len(out) > 4000 else (out or "[no output]")
    except subprocess.TimeoutExpired:
        return f"[Timeout] Command exceeded {CFG['tool_timeout']}s"
    except Exception as e:
        return f"[Error] {e}"


@tool
def Glob(pattern: str) -> str:
    """Find files matching a glob pattern inside the workspace (e.g. 'backend/**/*.py')."""
    try:
        ws      = Path(CFG["workspace"])
        matches = sorted(ws.glob(pattern))
        if not matches:
            return f"[No matches] {pattern}"
        rel = [str(m.relative_to(ws)).replace("\\", "/") for m in matches[:200]]
        suf = f"\n... and {len(matches)-200} more" if len(matches) > 200 else ""
        return "\n".join(rel) + suf
    except Exception as e:
        return f"[Error] {e}"


@tool
def Grep(pattern: str, path: str = ".", include: str = "") -> str:
    """Search for a text/regex pattern recursively in workspace files."""
    try:
        cmd = ["grep", "-r", "-n"] + ([f"--include={include}"] if include else []) + [pattern, path]
        r   = subprocess.run(cmd, capture_output=True, text=True,
                             cwd=CFG["workspace"], timeout=15,
                             encoding="utf-8", errors="replace")
        out = r.stdout.strip()
        if not out:
            return f"[No matches] pattern='{pattern}'"
        lines = out.splitlines()
        suf   = f"\n... ({len(lines)-80} more lines)" if len(lines) > 80 else ""
        return "\n".join(lines[:80]) + suf
    except Exception as e:
        return f"[Error] {e}"


@tool
def TodoWrite(todos: list[dict]) -> str:
    """Record a task list for the current session.
    Each todo: {id, content, status: pending|in_progress|done, priority: high|medium|low}"""
    _session["todos"][:] = todos
    icons = {"pending": "○", "in_progress": "◐", "done": "●"}
    lines = [
        f"{icons.get(t.get('status','pending'),'○')} [{t.get('priority','med')}] {t.get('content','')}"
        for t in todos
    ]
    return "TODOs updated:\n" + "\n".join(lines)


ALL_TOOLS = [Read, CreateFile, Write, Edit, Bash, Glob, Grep, TodoWrite]
TOOL_MAP  = {t.name: t for t in ALL_TOOLS}

# ══════════════════════════════════════════════════════════════════════════
# AGENT LOADER
# ══════════════════════════════════════════════════════════════════════════
def _parse_frontmatter(md: str) -> dict:
    meta: dict = {}
    m = re.match(r"^---\s*\n([\s\S]*?)\n---", md)
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                k, _, v = line.partition(":")
                meta[k.strip()] = v.strip()
    return meta

def load_agents() -> dict[str, dict]:
    candidates = [
        Path(CFG["workspace"]) / CFG["agents_dir"],
        Path(CFG["agents_dir"]),
    ]
    agents_path = next((p for p in candidates if p.exists()), None)
    if not agents_path:
        log.warning(f"Agents dir not found: {CFG['agents_dir']}")
        return {}
    agents: dict = {}
    for f in sorted(agents_path.glob("*.md")):
        content = f.read_text(encoding="utf-8", errors="replace")
        meta    = _parse_frontmatter(content)
        aid     = meta.get("name", f.stem)
        agents[aid] = {
            "id":           aid,
            "name":         aid.replace("-", " ").title(),
            "description":  meta.get("description", ""),
            "model":        meta.get("model", CFG["model"]),
            "system_prompt": content + FILE_CREATION_RULES,
        }
    log.info(f"Loaded {len(agents)} agents from {agents_path}")
    return agents

# ══════════════════════════════════════════════════════════════════════════
# LLM FACTORY
# ══════════════════════════════════════════════════════════════════════════
def make_llm(model: str | None = None, temperature: float = 0.3) -> ChatOllama:
    return ChatOllama(
        base_url=CFG["ollama_host"],
        model=model or CFG["model"],
        temperature=temperature,
        num_predict=4096,
    )

# ══════════════════════════════════════════════════════════════════════════
# GRAPH BUILDERS
# ══════════════════════════════════════════════════════════════════════════

# ── Single-agent graph ─────────────────────────────────────────────────────
def build_single_graph(agent_def: dict, model_override: str | None = None):
    """Compile a single ReAct agent graph using create_react_agent."""
    llm = make_llm(model_override or agent_def.get("model"))
    return create_react_agent(
        model=llm,
        tools=ALL_TOOLS,
        state_modifier=agent_def["system_prompt"],
        name=agent_def["id"],
    )


# ── Team (supervisor) graph state ─────────────────────────────────────────
class TeamState(TypedDict):
    messages:    Annotated[list[BaseMessage], add_messages]
    task:        str
    assignments: list[dict]   # [{agent, task}]
    dispatched:  list[str]    # agent IDs already called


PLANNER_SYSTEM = """\
You are the Engineering Team Lead.

Your job:
1. Use tools (Glob, Grep, Read) to understand the relevant codebase areas.
2. Decide which 1–3 specialist agents to involve.
3. End your reply with a JSON plan — the LAST thing you write, on its own line:

{{"assessment": "what needs doing", "assignments": [{{"agent": "agent-id", "task": "specific task with file paths and context"}}]}}

Available agents: {agents}
Task: {task}
"""


def build_team_graph(
    agents: dict[str, dict],
    model_override: str | None = None,
) -> Any:
    """
    StateGraph layout:
      START → planner → router → <agent-N> → router → ... → END
    """
    agent_ids = list(agents.keys())

    # ── Planner node ──────────────────────────────────────────────────────
    def planner_node(state: TeamState) -> dict:
        task     = state.get("task", "")
        ag_list  = ", ".join(agent_ids)
        system   = PLANNER_SYSTEM.format(agents=ag_list, task=task)
        llm      = make_llm(model_override, temperature=0.1)
        ag_graph = create_react_agent(llm, ALL_TOOLS, state_modifier=system, name="planner")

        result   = ag_graph.invoke({"messages": [HumanMessage(content=f"Analyze and plan for: {task}")]})
        return {"messages": result["messages"]}

    # ── Router node ───────────────────────────────────────────────────────
    def router_node(state: TeamState) -> dict:
        """
        Parse the most recent AI message for the plan JSON.
        Update `assignments` and `dispatched` accordingly.
        """
        dispatched  = list(state.get("dispatched", []))
        assignments = list(state.get("assignments", []))

        if not assignments:
            # First pass: extract plan from planner output
            for msg in reversed(state["messages"]):
                if isinstance(msg, AIMessage):
                    content = _strip_think(msg.content or "")
                    m = re.search(r'\{[\s\S]*?"assignments"[\s\S]*?\}', content)
                    if m:
                        try:
                            plan = json.loads(m.group(0))
                            assignments = plan.get("assignments", [])
                        except json.JSONDecodeError:
                            pass
                    break

        # Mark the last dispatched agent as done (if returning from one)
        # The last message author (if it's an agent) should be in dispatched
        return {"assignments": assignments, "dispatched": dispatched}

    # ── Routing function ──────────────────────────────────────────────────
    def choose_next(state: TeamState) -> str:
        dispatched  = set(state.get("dispatched", []))
        assignments = state.get("assignments", [])
        for a in assignments:
            agent_id = a.get("agent", "")
            if agent_id not in dispatched and agent_id in agent_ids:
                return agent_id
        return END

    # ── Per-agent wrapper nodes ───────────────────────────────────────────
    def make_agent_node(aid: str, agent_def: dict):
        def agent_node(state: TeamState) -> dict:
            # Find this agent's task from the assignments
            assignments = state.get("assignments", [])
            subtask     = next((a["task"] for a in assignments if a.get("agent") == aid), state.get("task", ""))

            llm      = make_llm(model_override or agent_def.get("model"))
            ag_graph = create_react_agent(
                llm, ALL_TOOLS,
                state_modifier=agent_def["system_prompt"],
                name=aid,
            )
            result = ag_graph.invoke({"messages": [HumanMessage(content=subtask)]})

            new_dispatched = list(state.get("dispatched", [])) + [aid]
            return {"messages": result["messages"], "dispatched": new_dispatched}

        return agent_node

    # ── Build StateGraph ──────────────────────────────────────────────────
    builder = StateGraph(TeamState)

    builder.add_node("planner", planner_node)
    builder.add_node("router",  router_node)
    for aid, adef in agents.items():
        builder.add_node(aid, make_agent_node(aid, adef))

    builder.add_edge(START,     "planner")
    builder.add_edge("planner", "router")

    # After router decides, go to the chosen agent or END
    all_targets = {aid: aid for aid in agent_ids}
    all_targets[END] = END
    builder.add_conditional_edges("router", choose_next, all_targets)

    # After each agent, always go back to router to decide next
    for aid in agent_ids:
        builder.add_edge(aid, "router")

    return builder.compile()


# ══════════════════════════════════════════════════════════════════════════
# SSE EVENT STREAM — maps LangGraph events → our frontend protocol
# ══════════════════════════════════════════════════════════════════════════
def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


async def stream_graph_events(graph, inputs: dict, config: dict | None = None):
    """
    Consume LangGraph astream_events and yield SSE strings
    that match the frontend's expected event protocol.
    """
    _artifacts_seen: set[str] = set()
    _current_agent: str       = ""

    yield _sse({"type": "run_start"})

    async for event in graph.astream_events(inputs, config or {}, version="v2"):
        kind     = event["event"]
        name     = event.get("name", "")
        data     = event.get("data", {})
        metadata = event.get("metadata", {})
        tags     = event.get("tags", [])

        # ── Identify current outer node (agent) ────────────────────────
        # LangGraph embeds the outer node name in metadata["langgraph_node"]
        # For nested subgraphs (create_react_agent), use tags to trace.
        lg_node  = metadata.get("langgraph_node", "")

        agents   = load_agents()
        agent_ids = list(agents.keys())

        if lg_node in agent_ids:
            _current_agent = lg_node
        elif lg_node == "planner":
            _current_agent = "team-lead"

        # ── Chain / node lifecycle ─────────────────────────────────────
        if kind == "on_chain_start":
            if lg_node in agent_ids:
                yield _sse({"type": "agent_start", "agent": lg_node})
            elif lg_node == "planner":
                yield _sse({"type": "agent_start", "agent": "team-lead"})

        elif kind == "on_chain_end":
            if lg_node in agent_ids:
                yield _sse({"type": "agent_done",  "agent": lg_node,
                            "todos": _session["todos"]})
            elif lg_node == "planner":
                yield _sse({"type": "agent_done",  "agent": "team-lead",
                            "todos": _session["todos"]})

        # ── Tool invocations ───────────────────────────────────────────
        elif kind == "on_tool_start":
            raw_input = data.get("input", {})
            if isinstance(raw_input, str):
                try:
                    raw_input = json.loads(raw_input)
                except Exception:
                    raw_input = {"input": raw_input}
            yield _sse({
                "type":  "tool_call",
                "agent": _current_agent,
                "tool":  name,
                "args":  raw_input,
            })

        elif kind == "on_tool_end":
            raw_output = data.get("output", "")
            # output might be a ToolMessage or plain string
            if isinstance(raw_output, ToolMessage):
                result = raw_output.content
            elif isinstance(raw_output, str):
                result = raw_output
            else:
                result = str(raw_output)

            yield _sse({
                "type":   "tool_result",
                "agent":  _current_agent,
                "tool":   name,
                "result": result[:500],
                "full":   result,
            })

            # Detect successful CreateFile → emit artifact_created
            if name == "CreateFile" and result.startswith("[OK]"):
                new_arts = [a for a in _session["artifacts"] if a["path"] not in _artifacts_seen]
                for art in new_arts:
                    _artifacts_seen.add(art["path"])
                    yield _sse({
                        "type":        "artifact_created",
                        "agent":       _current_agent,
                        **art,
                    })

        # ── Chat model final response ──────────────────────────────────
        elif kind == "on_chat_model_end":
            output = data.get("output")
            if not output:
                continue
            content    = _strip_think(getattr(output, "content", "") or "")
            tool_calls = getattr(output, "tool_calls", []) or []

            # Only emit text if this is a final (non-tool-calling) response
            if content and not tool_calls and _current_agent:
                yield _sse({
                    "type":    "agent_response",
                    "agent":   _current_agent,
                    "content": content,
                })

        # ── Router / plan extraction (team mode) ──────────────────────
        elif kind == "on_chain_end" and lg_node == "router":
            output = data.get("output", {})
            if isinstance(output, dict):
                assignments = output.get("assignments", [])
                dispatched  = output.get("dispatched", [])
                if assignments and not dispatched:
                    # First router pass — share the plan with UI
                    yield _sse({
                        "type": "team_plan",
                        "plan": {
                            "assignments": assignments,
                        },
                    })
                elif assignments and dispatched:
                    next_agent = next(
                        (a["agent"] for a in assignments if a.get("agent") not in dispatched),
                        None
                    )
                    if next_agent:
                        yield _sse({
                            "type":  "team_dispatch",
                            "agent": next_agent,
                            "step":  len(dispatched) + 1,
                        })

    yield _sse({
        "type":      "run_done",
        "artifacts": _session["artifacts"],
        "file_log":  _session["file_log"],
        "todos":     _session["todos"],
    })


# ══════════════════════════════════════════════════════════════════════════
# FASTAPI APPLICATION
# ══════════════════════════════════════════════════════════════════════════
app = FastAPI(title="Agent Team Server (LangGraph)", version="4.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}


@app.get("/api/health")
async def health():
    async with httpx.AsyncClient() as c:
        try:
            r      = await c.get(f"{CFG['ollama_host']}/api/tags", timeout=5)
            models = [m["name"] for m in r.json().get("models", [])]
            return {
                "status":           "ok",
                "backend":          "langgraph",
                "ollama":           CFG["ollama_host"],
                "models":           models,
                "workspace_exists": Path(CFG["workspace"]).exists(),
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}


@app.get("/api/config")
async def get_config():
    return {k: v for k, v in CFG.items()}


@app.post("/api/config")
async def set_config(body: dict):
    for k, v in body.items():
        if k in CFG:
            CFG[k] = v
            log.info(f"Config: {k} = {v}")
    return {"status": "ok", "config": CFG}


@app.get("/api/agents")
async def get_agents():
    return load_agents()


@app.get("/api/ollama/models")
async def get_models():
    async with httpx.AsyncClient() as c:
        try:
            r = await c.get(f"{CFG['ollama_host']}/api/tags", timeout=6)
            return r.json()
        except Exception as e:
            return {"error": str(e)}


@app.get("/api/run")
async def run_single(
    agent: str = Query(..., description="Agent ID"),
    task:  str = Query(..., description="Task for the agent"),
    model: str = Query(None),
):
    """Run a single agent with a full ReAct loop; stream SSE events."""
    _reset_session()
    agents = load_agents()
    if agent not in agents:
        return {"error": f"Agent '{agent}' not found"}

    graph = build_single_graph(agents[agent], model_override=model)
    inputs = {"messages": [HumanMessage(content=task)]}

    return StreamingResponse(
        stream_graph_events(graph, inputs),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )


@app.get("/api/team")
async def run_team(
    task:  str = Query(..., description="High-level task for the team"),
    model: str = Query(None),
):
    """Team-lead plans, then delegates to specialist agents via StateGraph."""
    _reset_session()
    agents = load_agents()
    if not agents:
        async def err():
            yield _sse({"type": "error", "message": "No agents found. Check agents_dir config."})
        return StreamingResponse(err(), media_type="text/event-stream", headers=SSE_HEADERS)

    graph  = build_team_graph(agents, model_override=model)
    inputs = {
        "messages":    [HumanMessage(content=task)],
        "task":        task,
        "assignments": [],
        "dispatched":  [],
    }

    return StreamingResponse(
        stream_graph_events(graph, inputs),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )


@app.get("/api/artifacts")
async def get_artifacts():
    return {
        "artifacts": _session["artifacts"],
        "file_log":  _session["file_log"],
        "todos":     _session["todos"],
    }


@app.get("/api/workspace")
async def list_workspace(path: str = ""):
    try:
        base   = Path(CFG["workspace"])
        target = (base / path).resolve() if path else base.resolve()
        if not target.is_dir():
            return {"error": "Not a directory"}
        items  = []
        for item in sorted(target.iterdir()):
            try:
                rel = str(item.relative_to(base)).replace("\\", "/")
                items.append({
                    "name":   item.name,
                    "path":   rel,
                    "is_dir": item.is_dir(),
                    "size":   item.stat().st_size if item.is_file() else None,
                })
            except Exception:
                pass
        return {"items": items, "workspace": str(base)}
    except Exception as e:
        return {"error": str(e)}


# ══════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Agent Team Server (LangGraph)")
    parser.add_argument("--host",      default="127.0.0.1")
    parser.add_argument("--port",      type=int, default=7788)
    parser.add_argument("--workspace", default=CFG["workspace"])
    parser.add_argument("--agents",    default=CFG["agents_dir"])
    parser.add_argument("--model",     default=CFG["model"])
    parser.add_argument("--ollama",    default=CFG["ollama_host"])
    args = parser.parse_args()

    CFG.update(
        workspace  = args.workspace,
        agents_dir = args.agents,
        model      = args.model,
        ollama_host= args.ollama,
    )
    for k, v in CFG.items():
        log.info(f"  {k:16}: {v}")

    import uvicorn
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")