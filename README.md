# RAG & Multi-Agent Exploration
> A hands-on learning repository — RAG pipelines, LangGraph agents, smolagents, and FastAPI backends, all running on local Ollama models.

---

## Overview

This repository is a collection of progressively complex AI experiments:

| Module | What it covers |
|---|---|
| `basic-rag/` | Retrieve → Generate pipeline using ChromaDB + Ollama |
| `reflective-rag/` | Generate → Critique → Refine loop with RAGAS evaluation |
| `retriever/` | Shared ChromaDB and FAISS retrieval utilities |
| `evaluator/` | RAGAS metrics (faithfulness, relevancy, precision, recall) |
| `agent/` | Standalone calculator agent and LangGraph agent-team server |
| `multi_agent/` | Full multi-agent system: Calculator + Mall + Orchestrator + Web UI |
| `agent-app/` | IT access management system using smolagents |
| `smolagent/` | Minimal smolagents experiments |
| `credentials/` | Credential management application |

All modules run entirely locally — no OpenAI required.

---

## Local Model Stack (Ollama)

| Role | Model |
|---|---|
| Supervisor / default | `deepseek-r1:7b` / `deepseek-r1:14b` |
| Strong reasoning | `qwen3:30b-instruct` |
| Light / fast | `qwen3:4b-instruct` / `llama3.1:8b` |
| RAG embeddings | `nomic-embed-text` |
| Semantic search (local) | `all-MiniLM-L6-v2` (bundled in `multi_agent/data/model/`) |
| RAGAS judge | `qwen3:30b-instruct` + `nomic-embed-text` |

Configure the Ollama host in `.env` (copy from `.env.example`):

```env
LLM_URL=http://<your-ollama-host>/api/generate
MODEL_DEFAULT=deepseek-r1:7b
MODEL_FAST=llama3.1:8b
MODEL_STRONG=qwen3:30b-instruct
MODEL_LIGHT=qwen3:4b-instruct
```

---

## Project Structure

```
.
├── basic-rag/
│   ├── main.py          # Interactive terminal chat
│   ├── pipeline.py      # retrieve_chroma → generate_answer
│   └── generator.py
│
├── reflective-rag/
│   ├── main.py          # Interactive terminal chat
│   ├── pipeline.py      # retrieve → answer → critique → refine → evaluate
│   └── response.py      # generate_answer, generate_critique, refine_answer
│
├── retriever/
│   ├── chroma.py        # ChromaDB retrieval (in-memory, threshold filtering)
│   ├── faissy.py        # FAISS retrieval
│   └── embedding.py
│
├── evaluator/
│   └── ragas_eval.py    # RAGAS evaluation (faithfulness, relevancy, precision, recall)
│
├── documents/
│   └── documents.py     # Document corpus loaded into ChromaDB
│
├── agent/
│   ├── calculator.py         # Production-style calculator agent (LangChain tools)
│   ├── agent_team_langgraph.py  # Agent team server — SSE streaming, dynamic agent loading
│   └── agent_team_ui.html    # Frontend for agent team server
│
├── multi_agent/
│   ├── main.py               # CLI entry point
│   ├── app.py                # FastAPI app with web UI
│   ├── agent/
│   │   ├── calculator.py     # Calculator agent
│   │   ├── mall.py           # Mall agent (search, booking)
│   │   ├── analytic.py       # Analytics agent
│   │   └── orchestrator.py   # Supervisor — classifies and routes queries
│   ├── graph/
│   │   └── workflow.py       # LangGraph StateGraph definition
│   ├── tools/
│   │   ├── calculator_tools.py
│   │   ├── mall_tool.py      # FAISS semantic search over store data
│   │   └── analytics_tool.py
│   ├── data/
│   │   ├── stores.json        # Store & product catalogue
│   │   ├── faiss.index        # FAISS index for product search
│   │   └── model/all-MiniLM-L6-v2/   # Local sentence-transformer model
│   ├── api/                   # FastAPI routes and session management
│   ├── static/                # JS + CSS for web UI
│   └── templates/index.html   # Web UI entry point
│
├── agent-app/
│   ├── main.py                # FastAPI app
│   ├── agents/
│   │   ├── lead_agent.py      # Supervisor (smolagents CodeAgent)
│   │   ├── document_agent.py  # Credential extraction + JSON normalisation
│   │   ├── system_access_agent.py  # Jira provisioning
│   │   └── audit_agent.py     # Compliance audit log
│   ├── tools/
│   │   ├── credential_tool.py
│   │   ├── jira_tool.py
│   │   └── audit_tool.py
│   └── api/routes.py
│
├── smolagent/
│   ├── basic.py          # Minimal CodeAgent with HF InferenceClientModel
│   ├── internal.py
│   └── tool.py
│
├── credentials/
│   └── app/              # Credential management (DB, LLM, security, services)
│
├── .env.example
└── load_env.py
```

---

## Modules

### Basic RAG

Straightforward retrieve-then-generate pipeline.

```
Query → ChromaDB retrieval (top-k, distance threshold) → Ollama generation → Answer
```

```bash
python -m basic-rag.main
```

---

### Reflective RAG

Adds a self-critique and refinement step, plus optional RAGAS evaluation.

```
Query → Retrieve → Generate → Critique → (if invalid) Refine → (optional) Evaluate
```

```bash
python -m reflective-rag.main
```

To evaluate with ground truth, call `agentic_rag_pipeline(query, ground_truth="...")` directly.

RAGAS metrics computed: **faithfulness**, **answer relevancy**, **context precision**, **context recall**.

---

### Multi-Agent System (`multi_agent/`)

A supervisor-pattern multi-agent system with a web UI.

**Architecture:**

```
User Query
    │
    ▼
Orchestrator (supervisor)
    │
    ├── Calculator Agent   → arithmetic, cost breakdowns
    ├── Mall Agent         → product search, store lookup, order booking
    │       └── Calculator Subgraph  (auto-triggered on confirmed orders)
    ├── Analytic Agent     → analytics queries
    └── Fallback           → unrecognised queries
```

**Key features:**
- FAISS + `all-MiniLM-L6-v2` for semantic product/store search (runs fully offline)
- Auto-handoff: when a mall order is confirmed, the Calculator subgraph computes subtotal, tax, and grand total without extra user input
- Confirmation word detection — short replies like `yes` or `ok` continue the previous agent's context
- Per-agent conversation history maintained within a session
- Web UI served via FastAPI (`/`) and chat endpoint (`POST /chat`)

**Run CLI:**
```bash
python -m multi_agent.main
```

**Run web UI:**
```bash
uvicorn multi_agent.app:app --reload
# Open http://localhost:8000
```

---

### Agent Team Server (`agent/agent_team_langgraph.py`)

A dynamic, file-driven agent team server built on LangGraph + FastAPI with SSE event streaming.

- Loads agent definitions from `.claude/agents/*.md` at runtime (no code change needed to add agents)
- Supports **single-agent mode** (one ReAct loop) and **team mode** (planner → router → specialist agents)
- Streams live events to the frontend: tool calls, tool results, agent responses, artifacts, todos
- Tools available to all agents: `Read`, `CreateFile`, `Write`, `Edit`, `Bash`, `Glob`, `Grep`, `TodoWrite`

```bash
python agent/agent_team_langgraph.py --workspace ./my-project --model qwen3:30b-instruct
```

API endpoints: `GET /api/run`, `GET /api/team`, `GET /api/agents`, `GET /api/artifacts`

---

### IT Access Management (`agent-app/`)

A multi-agent access provisioning system using **smolagents**.

```
Lead Agent (supervisor)
    ├── Document Agent     → extract & normalise credential JSON from user messages
    ├── System Access Agent → provision Jira access
    └── Audit Agent        → write compliance audit log
```

Models: `deepseek-r1:14b` (supervisor), `llama3.1:8b` (document + system), `qwen3:4b-instruct` (audit)

```bash
uvicorn agent-app.main:app --reload
```

---

### Standalone Calculator Agent (`agent/calculator.py`)

A production-style calculator agent with safe expression evaluation, no `eval()`.

Tools: `add`, `subtract`, `multiply`, `divide`, `power`, `sqrt`, `nth_root`, `percentage`, `percent_change`, `safe_eval`

```bash
python agent/calculator.py
```

---

## Setup

### 1. Install dependencies

```bash
pip install langchain langgraph langchain-ollama langchain-core \
            chromadb faiss-cpu sentence-transformers \
            smolagents datasets ragas \
            fastapi uvicorn httpx python-dotenv
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env with your Ollama host and model names
```

### 3. Pull Ollama models

```bash
ollama pull deepseek-r1:7b
ollama pull qwen3:30b-instruct
ollama pull qwen3:4b-instruct
ollama pull llama3.1:8b
ollama pull nomic-embed-text
```

---

## Built With

- [LangGraph](https://github.com/langchain-ai/langgraph) — agent orchestration and graph execution
- [LangChain](https://github.com/langchain-ai/langchain) — LLM tooling and agent primitives
- [smolagents](https://github.com/huggingface/smolagents) — lightweight code agents
- [ChromaDB](https://github.com/chroma-core/chroma) — vector store for RAG
- [FAISS](https://github.com/facebookresearch/faiss) — semantic search index
- [RAGAS](https://github.com/explodinggradients/ragas) — RAG evaluation metrics
- [FastAPI](https://fastapi.tiangolo.com/) — API layer
- [Ollama](https://ollama.com/) — local model inference
- Python 3.11+
