"""
agents.py — On-premise multi-agent team core
Requires: pip install ollama
Compatible with any Ollama model (qwen3:30b, qwen3.5:27b, etc.)
"""

import json
import re
from dataclasses import dataclass, field
from typing import Optional
import ollama


# ──────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────

DEFAULT_MODEL = "qwen3:30b-instruct"          # swap to qwen3.5:27b or any local model
OLLAMA_HOST   = "http://10.123.0.218:8080"

client = ollama.Client(host=OLLAMA_HOST)


# ──────────────────────────────────────────────
# Data models
# ──────────────────────────────────────────────

@dataclass
class Task:
    assignee: str
    title: str
    description: str
    priority: str = "medium"

@dataclass
class StatusUpdate:
    agent_id: str
    status_update: str
    collaborations: list[dict] = field(default_factory=list)

@dataclass
class TeamPlan:
    announcement: str
    tasks: list[Task]

@dataclass
class Message:
    from_id: str
    to_id: str          # agent id or "all"
    content: str
    msg_type: str       # announcement | update | collab | summary


# ──────────────────────────────────────────────
# Agent definitions
# ──────────────────────────────────────────────

AGENTS = {
    "lead": {
        "name": "Marcus Chen",
        "role": "CTO · Team Lead",
    },
    "pm": {
        "name": "Emma Walsh",
        "role": "Product Manager",
    },
    "backend": {
        "name": "Sarah Kim",
        "role": "Backend Engineer",
    },
    "frontend": {
        "name": "Alex Rivera",
        "role": "Frontend Engineer",
    },
    "ai": {
        "name": "Priya Patel",
        "role": "AI / ML Engineer",
    },
    "devops": {
        "name": "Jordan Lee",
        "role": "DevOps Engineer",
    },
}

MEMBER_ORDER = ["pm", "backend", "frontend", "ai", "devops"]


# ──────────────────────────────────────────────
# LLM helpers
# ──────────────────────────────────────────────

def _extract_json(text: str) -> dict:
    """Robustly extract a JSON object from model output."""
    # Strip markdown fences
    text = re.sub(r"```json\s*", "", text)
    text = re.sub(r"```\s*", "", text)
    # Strip <think>...</think> blocks (Qwen3 reasoning tokens)
    text = re.sub(r"<think>[\s\S]*?</think>", "", text, flags=re.IGNORECASE)
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Fallback: find the first {...} block
        m = re.search(r"\{[\s\S]*\}", text)
        if m:
            return json.loads(m.group(0))
        raise ValueError(f"No valid JSON found in model output:\n{text[:400]}")


def _chat(system: str, user: str, model: str = DEFAULT_MODEL) -> str:
    """Single-turn chat via Ollama."""
    response = client.chat(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
        options={"temperature": 0.7},
    )
    return response["message"]["content"]


# ──────────────────────────────────────────────
# Agent logic
# ──────────────────────────────────────────────

def team_lead_plan(project: str, model: str = DEFAULT_MODEL) -> TeamPlan:
    system = """You are Marcus Chen, CTO and Team Lead of a fast-moving startup.
Your team:
- Emma Walsh   (id: pm)      — Product Manager
- Sarah Kim    (id: backend) — Backend Engineer
- Alex Rivera  (id: frontend)— Frontend Engineer
- Priya Patel  (id: ai)      — AI / ML Engineer
- Jordan Lee   (id: devops)  — DevOps Engineer

Respond ONLY with a single valid JSON object. No extra text, no markdown fences:
{
  "announcement": "Your kickoff message to the team (2-3 energetic, specific sentences)",
  "tasks": [
    {
      "assignee": "pm|backend|frontend|ai|devops",
      "title": "Short task title",
      "description": "Concrete 2-sentence description",
      "priority": "high|medium|low"
    }
  ]
}
Include exactly one task per team member (all 5 members)."""

    raw = _chat(system, f"Project: {project}", model)
    data = _extract_json(raw)

    tasks = [Task(**t) for t in data["tasks"]]
    return TeamPlan(announcement=data["announcement"], tasks=tasks)


def member_respond(
    agent_id: str,
    task: Task,
    project: str,
    model: str = DEFAULT_MODEL,
) -> StatusUpdate:
    ag = AGENTS[agent_id]
    system = f"""You are {ag['name']}, {ag['role']} at a startup.
You report to Marcus Chen (CTO). Your project: "{project}"

Respond ONLY with a single valid JSON object. No extra text, no markdown fences:
{{
  "statusUpdate": "Your 2-3 sentence confident response to the CTO with your specific plan",
  "collaborations": [
    {{ "toAgent": "pm|backend|frontend|ai|devops", "message": "Specific coordination question or request" }}
  ]
}}
Include 1-2 collaborations only when there is a genuine cross-team dependency."""

    user = f"Your assigned task:\nTitle: {task.title}\nDetails: {task.description}"
    raw = _chat(system, user, model)
    data = _extract_json(raw)

    collabs = [
        c for c in data.get("collaborations", [])
        if c.get("toAgent") and c["toAgent"] != agent_id and c["toAgent"] in AGENTS
    ]
    return StatusUpdate(
        agent_id=agent_id,
        status_update=data["statusUpdate"],
        collaborations=collabs,
    )


def team_lead_summarize(
    project: str,
    responses: list[StatusUpdate],
    model: str = DEFAULT_MODEL,
) -> str:
    system = """You are Marcus Chen, CTO. Your team just reported back.
Respond ONLY with a single valid JSON object:
{"summary": "Your 2-sentence wrap-up: acknowledge team progress and state the immediate next step."}"""

    updates = [
        {"name": AGENTS[r.agent_id]["name"], "update": r.status_update}
        for r in responses
    ]
    raw = _chat(system, f"Project: {project}\nTeam updates: {json.dumps(updates)}", model)
    data = _extract_json(raw)
    return data["summary"]


# ──────────────────────────────────────────────
# Orchestrator
# ──────────────────────────────────────────────

def run_team(
    project: str,
    model: str = DEFAULT_MODEL,
    on_message=None,        # callback(Message) — for streaming to a UI
) -> list[Message]:
    """
    Full multi-agent team run.
    Returns the complete message log.
    If on_message is provided, each Message is dispatched as it's produced.
    """
    log: list[Message] = []

    def emit(msg: Message):
        log.append(msg)
        if on_message:
            on_message(msg)

    # Phase 1 — Team Lead plans
    plan = team_lead_plan(project, model)
    emit(Message("lead", "all", plan.announcement, "announcement"))

    task_map = {t.assignee: t for t in plan.tasks}

    # Phase 2 — Members respond
    responses: list[StatusUpdate] = []
    for mid in MEMBER_ORDER:
        task = task_map.get(mid)
        if not task:
            continue

        sr = member_respond(mid, task, project, model)
        responses.append(sr)

        # Status update → Team Lead
        emit(Message(mid, "lead", sr.status_update, "update"))

        # Cross-team collaboration messages
        for c in sr.collaborations:
            emit(Message(mid, c["toAgent"], c["message"], "collab"))

    # Phase 3 — Team Lead wraps up
    summary = team_lead_summarize(project, responses, model)
    emit(Message("lead", "all", summary, "summary"))

    return log
