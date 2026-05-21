#!/usr/bin/env python3
"""
Agent Team Server — WingBank ADE / On-Premise
=============================================
Local FastAPI server that orchestrates AI agents with real codebase access.
Each agent is loaded from .claude/agents/*.md and equipped with filesystem tools.

Install:
    pip install fastapi uvicorn httpx

Run:
    python agent_team_server.py
    python agent_team_server.py --workspace d:/development/wingbank-ade
    python agent_team_server.py --workspace /path/to/project --agents .claude/agents --port 7788

Then open agent_team_ui.html in your browser (or python -m http.server 8080).
"""

import argparse
import asyncio
import json
import logging
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import AsyncGenerator

import httpx
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse

# ══════════════════════════════════════════════════════════════
# LOGGING
# ══════════════════════════════════════════════════════════════
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("agent-team")

# ══════════════════════════════════════════════════════════════
# CONFIG  (env vars override defaults; CLI args override env)
# ══════════════════════════════════════════════════════════════
CFG = {
    "ollama_host":  os.getenv("OLLAMA_HOST",  "http://10.123.0.218:8080"),
    "model":        os.getenv("AGENT_MODEL",  "deepseek-r1:7b"),
    "workspace":    os.getenv("WORKSPACE",    ".agent-app"),
    "agents_dir":   os.getenv("AGENTS_DIR",   ".claude/agents"),
    "strip_think":  True,
    "max_tool_loops": 30,
    "tool_timeout":   60,   # seconds per bash command
    "read_max_lines": 300,  # truncate long files in tool results
}

# ══════════════════════════════════════════════════════════════
# TOOL DEFINITIONS  (Ollama function-calling format)
# ══════════════════════════════════════════════════════════════
TOOL_DEFS = [
    {
        "type": "function",
        "function": {
            "name": "Read",
            "description": "Read the full contents of a file in the workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path relative to workspace root."}
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "Write",
            "description": "Write (create or overwrite) a file in the workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path":    {"type": "string", "description": "File path relative to workspace root."},
                    "content": {"type": "string", "description": "Full content to write to the file."},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "Edit",
            "description": "Edit a file by replacing the first occurrence of old_str with new_str.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path":    {"type": "string"},
                    "old_str": {"type": "string", "description": "Exact string to search for (must be unique in the file)."},
                    "new_str": {"type": "string", "description": "Replacement string."},
                },
                "required": ["path", "old_str", "new_str"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "Bash",
            "description": "Execute a shell command in the workspace directory. Use for pytest, pnpm, grep, git, etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Shell command to run (cwd = workspace root)."},
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "Glob",
            "description": "Find files matching a glob pattern relative to the workspace root.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Glob pattern e.g. 'backend/**/*.py' or 'frontend/src/api/*.ts'"},
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "Grep",
            "description": "Search for a text pattern recursively in workspace files.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Text or regex pattern to search for."},
                    "path":    {"type": "string", "description": "Subdirectory to search in (default: '.' = whole workspace)."},
                    "include": {"type": "string", "description": "File glob filter e.g. '*.py', '*.ts' (optional)."},
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "TodoWrite",
            "description": "Record a task list for the current work session (stored server-side).",
            "parameters": {
                "type": "object",
                "properties": {
                    "todos": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id":       {"type": "string"},
                                "content":  {"type": "string"},
                                "status":   {"type": "string", "enum": ["pending", "in_progress", "done"]},
                                "priority": {"type": "string", "enum": ["high", "medium", "low"]},
                            },
                        },
                    },
                },
                "required": ["todos"],
            },
        },
    },
]

# ══════════════════════════════════════════════════════════════
# TOOL EXECUTION
# ══════════════════════════════════════════════════════════════
_todos: list = []  # in-memory session todos
_file_log: list = []  # files accessed this session

def _workspace_path(relative: str) -> Path:
    """Resolve a relative path safely inside the workspace."""
    ws = Path(CFG["workspace"]).resolve()
    target = (ws / relative.lstrip("/\\")).resolve()
    try:
        target.relative_to(ws)
    except ValueError:
        raise PermissionError(f"Path '{relative}' is outside workspace")
    return target

def execute_tool(name: str, args: dict) -> str:
    """Execute a tool synchronously, return string result."""
    global _todos, _file_log
    try:
        if name == "Read":
            path = _workspace_path(args["path"])
            if not path.exists():
                return f"[Error] File not found: {args['path']}"
            content = path.read_text(encoding="utf-8", errors="replace")
            lines = content.splitlines()
            _file_log.append({"action": "read", "path": args["path"]})
            if len(lines) > CFG["read_max_lines"]:
                preview = "\n".join(lines[:CFG["read_max_lines"]])
                return f"{preview}\n\n[... {len(lines) - CFG['read_max_lines']} more lines — use Bash grep/sed for targeted reading ...]"
            return content

        elif name == "Write":
            path = _workspace_path(args["path"])
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(args["content"], encoding="utf-8")
            _file_log.append({"action": "write", "path": args["path"], "bytes": len(args["content"])})
            return f"[OK] Written {len(args['content'].encode())} bytes → {args['path']}"

        elif name == "Edit":
            path = _workspace_path(args["path"])
            if not path.exists():
                return f"[Error] File not found: {args['path']}"
            content = path.read_text(encoding="utf-8")
            old = args["old_str"]
            if old not in content:
                # Show surrounding context to help the agent fix the mismatch
                idx = content.lower().find(old[:30].lower())
                hint = f"\n  Nearby text at char ~{idx}: ...{content[max(0,idx-50):idx+100]}..." if idx >= 0 else ""
                return f"[Error] old_str not found in {args['path']}.{hint}"
            new_content = content.replace(old, args["new_str"], 1)
            path.write_text(new_content, encoding="utf-8")
            _file_log.append({"action": "edit", "path": args["path"]})
            return f"[OK] Edited {args['path']} — replaced {len(old)} chars with {len(args['new_str'])} chars"

        elif name == "Bash":
            cmd = args["command"]
            log.info(f"Bash: {cmd}")
            is_windows = sys.platform.startswith("win")
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                cwd=CFG["workspace"],
                timeout=CFG["tool_timeout"],
                encoding="utf-8",
                errors="replace",
            )
            output = ""
            if result.stdout:
                output += result.stdout
            if result.stderr:
                output += ("\n[stderr]\n" if result.stdout else "") + result.stderr
            output = output.strip()
            if result.returncode != 0:
                output = f"[exit {result.returncode}]\n{output}"
            return (output[:4000] + f"\n[... truncated]") if len(output) > 4000 else (output or "[no output]")

        elif name == "Glob":
            ws = Path(CFG["workspace"])
            pattern = args["pattern"]
            try:
                matches = sorted(ws.glob(pattern))
            except Exception as e:
                return f"[Error] Invalid glob pattern: {e}"
            if not matches:
                return f"[No files matched] pattern: {pattern}"
            rel = [str(m.relative_to(ws)).replace("\\", "/") for m in matches[:200]]
            suffix = f"\n... and {len(matches)-200} more" if len(matches) > 200 else ""
            return "\n".join(rel) + suffix

        elif name == "Grep":
            pattern = args["pattern"]
            search_in = args.get("path", ".")
            include = args.get("include", "")
            cmd_parts = ["grep", "-r", "-n", "--include=" + include if include else None, pattern, search_in]
            cmd_parts = [x for x in cmd_parts if x]
            result = subprocess.run(
                cmd_parts, capture_output=True, text=True,
                cwd=CFG["workspace"], timeout=15, encoding="utf-8", errors="replace"
            )
            out = result.stdout.strip()
            if not out:
                return f"[No matches] pattern: {pattern}"
            lines = out.splitlines()[:80]
            suffix = f"\n... ({len(out.splitlines())-80} more lines)" if len(out.splitlines()) > 80 else ""
            return "\n".join(lines) + suffix

        elif name == "TodoWrite":
            _todos = args.get("todos", [])
            icons = {"pending": "○", "in_progress": "◐", "done": "●"}
            lines = [f"{icons.get(t.get('status','pending'),'○')} [{t.get('priority','med')}] {t.get('content','')}" for t in _todos]
            return "TODO updated:\n" + "\n".join(lines)

        else:
            return f"[Error] Unknown tool: {name}"

    except PermissionError as e:
        return f"[PermissionError] {e}"
    except subprocess.TimeoutExpired:
        return f"[Timeout] Command exceeded {CFG['tool_timeout']}s"
    except Exception as e:
        log.exception(f"Tool {name} failed")
        return f"[Error] {type(e).__name__}: {e}"


# ══════════════════════════════════════════════════════════════
# AGENT DEFINITIONS LOADER
# ══════════════════════════════════════════════════════════════
def _parse_frontmatter(md: str) -> dict:
    meta = {}
    m = re.match(r"^---\s*\n([\s\S]*?)\n---", md)
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                k, _, v = line.partition(":")
                k = k.strip(); v = v.strip()
                if k == "tools":
                    v = [t.strip().strip("[]'\"") for t in re.split(r",\s*", v.strip("[]"))]
                meta[k] = v
    return meta

def load_agents() -> dict:
    """Load all .md files from the configured agents directory."""
    agents_path = Path(CFG["workspace"]) / CFG["agents_dir"]
    if not agents_path.exists():
        # Fallback: relative to cwd
        agents_path = Path(CFG["agents_dir"])
    
    agents = {}
    if not agents_path.exists():
        log.warning(f"Agents directory not found: {agents_path}")
        return agents

    for f in sorted(agents_path.glob("*.md")):
        content = f.read_text(encoding="utf-8", errors="replace")
        meta = _parse_frontmatter(content)
        agent_id = meta.get("name", f.stem)
        agents[agent_id] = {
            "id":           agent_id,
            "name":         agent_id.replace("-", " ").title(),
            "description":  meta.get("description", ""),
            "model":        meta.get("model", CFG["model"]),
            "tools":        meta.get("tools", []),
            "system_prompt": content,
            "file":         str(f),
        }
        log.info(f"Loaded agent: {agent_id}")

    return agents


# ══════════════════════════════════════════════════════════════
# OLLAMA CALL (with tool loop)
# ══════════════════════════════════════════════════════════════
def _strip_think(text: str) -> str:
    if CFG["strip_think"] and text:
        text = re.sub(r"<think>[\s\S]*?</think>", "", text, flags=re.IGNORECASE)
    return text.strip()

def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

async def run_agent_sse(
    agent_id: str,
    task: str,
    extra_context: str = "",
    model_override: str = None,
) -> AsyncGenerator[str, None]:
    """Run one agent with tool-calling loop; yield SSE strings."""

    agents = load_agents()
    agent = agents.get(agent_id)
    if not agent:
        yield _sse({"type": "error", "message": f"Agent '{agent_id}' not found in {CFG['agents_dir']}"})
        return

    model = model_override or agent["model"] or CFG["model"]
    system_prompt = agent["system_prompt"]
    if extra_context:
        system_prompt += f"\n\n---\n### Session Context\n{extra_context}"

    messages: list = [{"role": "user", "content": task}]
    yield _sse({"type": "agent_start", "agent": agent_id, "task": task, "model": model})

    iteration = 0
    async with httpx.AsyncClient(timeout=httpx.Timeout(180.0)) as client:
        while iteration < CFG["max_tool_loops"]:
            iteration += 1
            log.info(f"[{agent_id}] iteration {iteration}")

            try:
                resp = await client.post(
                    f"{CFG['ollama_host']}/api/chat",
                    json={
                        "model": model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            *messages,
                        ],
                        "tools":  TOOL_DEFS,
                        "stream": False,
                        "options": {"temperature": 0.3, "num_predict": 4096},
                    },
                )
                resp.raise_for_status()
                data = resp.json()
            except httpx.HTTPStatusError as e:
                yield _sse({"type": "error", "message": f"Ollama HTTP {e.response.status_code}: {e.response.text[:200]}"})
                return
            except Exception as e:
                yield _sse({"type": "error", "message": f"Ollama error: {e}"})
                return

            msg = data.get("message", {})
            content = _strip_think(msg.get("content") or "")
            tool_calls = msg.get("tool_calls") or []

            # Append assistant message (preserve tool_calls for context)
            assistant_msg: dict = {"role": "assistant", "content": content}
            if tool_calls:
                assistant_msg["tool_calls"] = tool_calls
            messages.append(assistant_msg)

            # Emit any text content even when there are also tool calls
            if content and not tool_calls:
                yield _sse({"type": "agent_response", "agent": agent_id, "content": content})

            if tool_calls:
                for tc in tool_calls:
                    fn  = tc.get("function", {})
                    fn_name = fn.get("name", "")
                    fn_args = fn.get("arguments", {})
                    if isinstance(fn_args, str):
                        try:
                            fn_args = json.loads(fn_args)
                        except Exception:
                            fn_args = {}

                    yield _sse({"type": "tool_call", "agent": agent_id, "tool": fn_name, "args": fn_args})

                    result = await asyncio.to_thread(execute_tool, fn_name, fn_args)

                    yield _sse({
                        "type":   "tool_result",
                        "agent":  agent_id,
                        "tool":   fn_name,
                        "args":   fn_args,
                        "result": result[:500],       # preview for UI
                        "full":   result,             # full content available
                    })

                    messages.append({"role": "tool", "content": result})

            else:
                # No more tool calls → agent finished
                break

    yield _sse({"type": "agent_done", "agent": agent_id, "todos": _todos})


async def run_team_sse(task: str, model_override: str = None) -> AsyncGenerator[str, None]:
    """
    Team-lead coordinates: analyzes the task, then delegates to domain agents.
    Yields a merged SSE stream.
    """
    global _file_log
    _file_log = []

    yield _sse({"type": "team_start", "task": task})

    # ── Step 1: Team-lead plans ──────────────────────────────
    planning_prompt = f"""
You are acting as team coordinator for this session.

TASK: {task}

First use your tools to understand the relevant parts of the codebase (Read, Glob, Grep) as needed.
Then respond with ONLY a JSON object (no markdown fences, no extra text):

{{
  "assessment": "2-3 sentence summary of what needs to be done and which files are involved",
  "assignments": [
    {{
      "agent": "exact-agent-id",
      "task": "Specific, detailed task with file paths and context so the agent can start immediately"
    }}
  ],
  "sequence": "sequential"
}}

Available agents: {", ".join(load_agents().keys())}
Use "sequential" (default) unless assignments are truly independent.
Keep assignments to 1–3 agents to stay focused.
""".strip()

    plan_content = ""
    async for event in run_agent_sse("team-lead", planning_prompt, model_override=model_override):
        yield event
        try:
            d = json.loads(event[6:])  # strip "data: "
            if d.get("type") == "agent_response":
                plan_content += d.get("content", "")
        except Exception:
            pass

    # ── Step 2: Parse plan ───────────────────────────────────
    plan = None
    try:
        # Extract JSON from plan_content
        m = re.search(r"\{[\s\S]*\}", plan_content)
        if m:
            plan = json.loads(m.group(0))
    except Exception:
        pass

    if not plan or not plan.get("assignments"):
        yield _sse({"type": "team_error", "message": "Team-lead did not return a valid delegation plan."})
        return

    yield _sse({"type": "team_plan", "plan": plan})

    # ── Step 3: Run each assigned agent ─────────────────────
    for i, assignment in enumerate(plan.get("assignments", [])):
        agent_id  = assignment.get("agent", "")
        subtask   = assignment.get("task", "")
        if not agent_id or not subtask:
            continue

        context = f"Project task: {task}\nYour specific assignment: {subtask}"
        yield _sse({"type": "team_dispatch", "agent": agent_id, "task": subtask, "step": i + 1})

        async for event in run_agent_sse(agent_id, subtask, extra_context=context, model_override=model_override):
            yield event

    yield _sse({"type": "team_done", "files_touched": _file_log})


# ══════════════════════════════════════════════════════════════
# FASTAPI APP
# ══════════════════════════════════════════════════════════════
app = FastAPI(title="Agent Team Server", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
async def health():
    async with httpx.AsyncClient() as client:
        try:
            r = await client.get(f"{CFG['ollama_host']}/api/tags", timeout=5)
            models = [m["name"] for m in r.json().get("models", [])]
            return {"status": "ok", "ollama": CFG["ollama_host"], "models": models, "workspace_exists": Path(CFG["workspace"]).exists()}
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
            log.info(f"Config updated: {k} = {v}")
    return {"status": "ok", "config": CFG}

@app.get("/api/agents")
async def get_agents():
    return load_agents()

@app.get("/api/ollama/models")
async def get_models():
    async with httpx.AsyncClient() as client:
        try:
            r = await client.get(f"{CFG['ollama_host']}/api/tags", timeout=6)
            return r.json()
        except Exception as e:
            return {"error": str(e)}

@app.get("/api/run")
async def run_single(
    agent: str = Query(..., description="Agent ID"),
    task:  str = Query(..., description="Task for the agent"),
    model: str = Query(None, description="Override model"),
):
    """Run a single agent; stream SSE."""
    global _file_log
    _file_log = []
    return StreamingResponse(
        run_agent_sse(agent, task, model_override=model),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

@app.get("/api/team")
async def run_team(
    task:  str = Query(..., description="High-level task for the team"),
    model: str = Query(None, description="Override model for all agents"),
):
    """Team-lead coordinates agents; stream SSE."""
    return StreamingResponse(
        run_team_sse(task, model_override=model),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

@app.get("/api/files")
async def get_file_log():
    return {"files": _file_log, "todos": _todos}

@app.get("/api/workspace")
async def list_workspace(path: str = Query("", description="Subpath within workspace")):
    try:
        base = Path(CFG["workspace"])
        target = (base / path).resolve() if path else base.resolve()
        if not target.is_dir():
            return {"error": "Not a directory", "path": str(target)}
        items = []
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


# ══════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Agent Team Server")
    parser.add_argument("--host",      default="127.0.0.1")
    parser.add_argument("--port",      type=int, default=7788)
    parser.add_argument("--workspace", default=CFG["workspace"], help="Absolute path to project root")
    parser.add_argument("--agents",    default=CFG["agents_dir"], help="Path to agents dir (relative to workspace)")
    parser.add_argument("--model",     default=CFG["model"], help="Default Ollama model")
    parser.add_argument("--ollama",    default=CFG["ollama_host"], help="Ollama base URL")
    args = parser.parse_args()

    CFG["workspace"]   = args.workspace
    CFG["agents_dir"]  = args.agents
    CFG["model"]       = args.model
    CFG["ollama_host"] = args.ollama

    log.info(f"Workspace : {CFG['workspace']}")
    log.info(f"Agents dir: {CFG['agents_dir']}")
    log.info(f"Model     : {CFG['model']}")
    log.info(f"Ollama    : {CFG['ollama_host']}")
    log.info(f"Server    : http://{args.host}:{args.port}")

    import uvicorn
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
