# Multi-Agent POC — Calculator + Mall
> Proof of Concept | LangGraph + LangChain

---

## Overview

This POC demonstrates a **multi-agent system** built with LangGraph where a
supervisor (orchestrator) automatically routes user queries to the right
specialised agent.

Two agents are currently implemented:

| Agent | Responsibility |
|---|---|
| **Calculator** | Basic arithmetic and order cost calculations |
| **Mall** | Product search, store lookup, and order booking |

When a mall order is confirmed, the system **automatically hands off** to the
Calculator agent to compute subtotal, tax, and grand total — no extra input
from the user required.

---

## Architecture

```
User Query
    │
    ▼
Orchestrator (supervisor)
    │
    ├── Calculator Agent   → math queries
    ├── Mall Agent         → shopping queries
    │       └── Calculator Subgraph  (auto-triggered on confirmed orders)
    └── Fallback           → unrecognised queries
```

The orchestrator also detects short confirmation words (`yes`, `ok`, `confirm`, etc.)
and automatically continues with the same agent from the previous turn,
enabling natural multi-turn conversations.

---

## Project Structure

```
.
├── main.py              # Entry point — interactive chat loop + CLI runner
├── graph.py             # LangGraph graph definition (nodes, edges, router)
├── config.py            # AgentConfig — loads settings from .env
├── .env.example         # Required environment variables (copy to .env)
├── examples.txt         # Sample queries and expected outputs for demo
└── src/
    ├── agent/
    │   └── orchestrator.py   # OrchestratorAgent — classifies and routes queries
    └── core/
        └── logger.py         # Logging setup
```

---

## Setup

### 1. Clone and install dependencies

```bash
pip install langchain langgraph langchain-openai python-dotenv
```

### 2. Configure environment variables

```bash
cp .env.example .env
# Open .env and fill in your API keys and settings
```

### 3. Run the POC

**Interactive mode** (recommended for demo):
```bash
python main.py
```

**Single query mode:**
```bash
python main.py --query "Find me a Nike running shoe"
python main.py --query "What is 25 multiplied by 4?"
```

---

## Example Session

```
================================================
  Multi-Agent POC — Calculator + Mall
  Type 'exit' to quit
================================================

You: find me a nike shoe
Agent: Here are some Nike shoes available:
       1. Nike Air Zoom Pegasus 40 — $129.99 (Level 2, SportsMall)
       Would you like to order any of these?

You: order 2 of those
Agent: 2x Nike Air Zoom Pegasus 40 at $129.99 each. Shall I confirm?

You: yes
Agent: Order confirmed!
       Subtotal : $259.98
       Tax (9%) : $23.40
       Total    : $283.38

You: what is 150 divided by 3
Agent: 150 divided by 3 equals 50.

You: exit
Goodbye!
```

---

## Key Design Decisions

**Supervisor pattern** — A single orchestrator node classifies every query
before any agent runs. This keeps routing logic centralised and easy to extend
(add a new agent by registering it in the registry and adding a node).

**Subgraph for calculator handoff** — The mall→calculator handoff uses a
compiled LangGraph subgraph rather than a direct function call. This keeps the
two agents properly isolated and makes the handoff traceable in LangSmith.

**Confirmation word detection** — Short replies like "yes" or "ok" are
intercepted at the orchestrator level so the user doesn't have to repeat
context. The system knows which agent was active last and continues seamlessly.

---

## Limitations (Known — out of scope for POC)

- History is maintained within a session only (no persistence across restarts)
- Only one agent runs per turn (no parallel agent execution)
- Fallback agent returns an error string rather than a helpful suggestion

---

## Next Steps (Post-POC)

- [ ] Persistent memory (save history to a database between sessions)
- [ ] Add more agents (e.g. loyalty points, promotions)
- [ ] Human-in-the-loop step for high-value order confirmation
- [ ] Deploy as an API endpoint (FastAPI wrapper around `run_query`)
- [ ] LangSmith evaluation for routing accuracy

---

## Built With

- [LangGraph](https://github.com/langchain-ai/langgraph) — agent orchestration and graph execution
- [LangChain](https://github.com/langchain-ai/langchain) — LLM tooling and agent primitives
- Python 3.11+
