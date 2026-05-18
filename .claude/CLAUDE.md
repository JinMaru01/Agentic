# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ADE (Analytics & Decision Engine) is a full-stack web application for managing ML workflows and data pipelines at Wingbank. It consists of a FastAPI backend and a React/TypeScript frontend. The system handles flow configuration, execution, audit trails, ML model registry, and a SQL automation module.

## Commands

### Backend

All backend commands run from the `backend/` directory with the `.venv` activated:

```bash
# Activate venv (Windows)
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the server
python main.py

# Run all tests
pytest

# Run a single test file
pytest app/tests/api/routes/test_auth_api.py

# Run tests by marker
pytest -m health
```

The backend runs on port `8000` by default. API prefix is `/ade/api`. Swagger docs available at `http://localhost:8000/ade/api/docs`.

### Frontend

All frontend commands run from the `frontend/` directory:

```bash
npm install           # or pnpm install
pnpm dev              # dev server (http://localhost:5173/ade)
pnpm build            # production build (outputs to ../static)
pnpm lint             # ESLint
pnpm test             # Jest
pnpm test:watch       # Jest watch mode
pnpm test:coverage    # Jest with coverage
```

### Docker

```bash
docker-compose up         # run the full stack
docker-compose -f docker-compose-ade.yml up   # ADE-specific compose
```

### Building individual components (UMD)

```powershell
$env:VITE_SOURCE='./src/components/MyComponent.tsx'; pnpm build
```

## Architecture

### Backend

`backend/main.py` — FastAPI app entry point. Mounts all routers under `flowconfig.api_prefix` (`/ade/api`). Starts Redis local warmer and performance matrix on boot.

**Key layers:**

- `backend/flowcore/` — Core flow execution engine. `flowManager` loads flows from Redis cache (keyed as `flow_id:{id}`), compiles node graphs, and executes them. `modules.py` dynamically loads node-type implementations from `flowcore/internal/module/`.
- `backend/app/api/` — FastAPI route handlers grouped by domain: `auth`, `flowconfig`, `flowlist`, `audittrail`, `public`, `sas_main` (SQL automation), `oauth_microsoft`, and `settings/*`.
- `backend/app/api/__init__.py` — Central router registry; all sub-routers are included here.
- `backend/flow/` — SQLAlchemy ORM models (`dbschema/table/`), views (`dbschema/view/`), and services (`services/`).
- `backend/_lib/` — Shared infrastructure: Redis utilities, database connectors (PostgreSQL, Hive, MongoDB, S3/MinIO), HTML form builder, function registry, ETL utilities for C360.
- `backend/_config.py` — Database connection singletons for `flow`, `c360`, `datawh`, `redis`, `redislocal`, `mlapp`. Each reads config via `load_env_by_prefix()`.
- `backend/app_env/` — Environment loading. `.env`, `.env.office`, `.env.k8s-dev` files. `load_env_by_prefix("FLOWDB")` extracts vars like `FLOWDB_HOST`, `FLOWDB_PORT` into a dict with lowercase keys.
- `backend/app/auth/` — JWT (HS512) + AES cookie-based auth. Microsoft OAuth2 via `oauth_microsoft` router.

**Database connections** (prefix → purpose):
- `FLOWDB_*` → PostgreSQL schema `flow` (flow definitions, versions, config)
- `C360DB_*` → PostgreSQL schema `c360` (Customer 360 data)
- `REDISDB_*` / `REDISLOCALDB_*` → Redis (flow execution cache, sessions)
- `MLAPP_*` → PostgreSQL schema `mlapp` (ML registry)
- `POSTGRESSAS_*` → PostgreSQL schema `da_app` (SQL automation)
- `DATAWHDB_*` → Hive (data warehouse)

### Frontend

`frontend/src/pages/index.tsx` — React Router config. Base URL is `/ade`. Routes: `/login`, `/list` (flow list), `/config` (flow editor), `/flow/settings/*` (admin), `/model/registry/*` (MLflow), `/functions` (function manager), `/sql/*` (SQL automation).

**Key layers:**

- `frontend/src/context/AuthContext.tsx` — Global auth state. Provides `useAuth()` hook with `login`, `logout`, `user`, `isDeptRole`, `isBaseRole`. Role system: base roles (`admin`, `user`, `d_admin`) and department roles (`view`, `test`, `verify`, `publish`, `design`).
- `frontend/src/utils/axios.ts` — Axios instance using `baseURL` from `configs.ts`. `VITE_BaseUrl` overrides `VITE_BasePrefix`. Final base URL is `<prefix_or_url>/api`.
- `frontend/src/api/` — Per-domain API modules (auth, flowconfig, flowlist, audittrail, etc.).
- `frontend/src/components/FlowInputs/` — Dynamic form engine that renders form fields from backend-driven schemas.
- `frontend/src/components/FlowUIatoms/` — Shared UI primitives (buttons, alerts, stepper, tags, tooltip).
- `frontend/src/pages/flowlist/` — Main flow list/dashboard with charts and node design viewer.
- `frontend/src/pages/flowconfig/` — Flow configuration editor.
- `frontend/src/pages/sql_automation/` — SQL automation module with pending requests and activities views.

**Environment variables** (`frontend/.env`):
- `VITE_BaseUrl` — full backend base URL (e.g., `http://localhost:8000/ade`)
- `VITE_BasePrefix` — path prefix for same-origin deployments (e.g., `/ade`)
- `VITE_WSUrl` — WebSocket URL

### CI/CD

GitLab CI (`.gitlab-ci.yml`): `uat` branch triggers Docker build → push to Nexus registry → manual deploy to `mlop-dev-machine-learning` namespace via `kubectl set image`.

## Environment Setup

Backend environment files live in `backend/app_env/`. The active environment is selected by the `ENVIRONMENT` env var (defaults to `office`). Files are merged in order: `.env` → `.env.{ENVIRONMENT}` → `.env.local`.

All env var keys must be UPPERCASE — the loader raises if any are lowercase.

For local development, copy `backend/app_env/.env` and adjust DB hosts/credentials. The `office` environment points to `10.123.0.250` (PostgreSQL, Redis, Hive).

## Testing

Backend tests live in `backend/app/tests/`. The `pytest.ini` points `testpaths` to `app/tests`. Tests stop after 2 failures (`--maxfail=2`).

Frontend tests use Jest with `jest-environment-jsdom`. Test files follow `*.test.tsx` pattern. Place tests adjacent to source in `__tests__/` subdirectories.
