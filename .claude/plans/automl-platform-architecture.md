# AutoML Platform Architecture Plan — v2
### WingBank ADE — ML Workflow Design
**Reviewed by:** Software Architect + Engineering Lead | **Revised:** 2026-05-18

---

## Context

The ADE platform has a partial ML workflow (experiment → CSV upload → preprocessing → single-model training). This plan evolves it into a full AutoML platform with three capabilities:

1. **Online AutoML** — browser-based: configure data + target, system trains all models with hyperparameter optimization in parallel, returns a ranked leaderboard, user registers the winner
2. **Offline SDK workflow** — data scientist trains locally using the `mlapp` Python SDK pointing to ADE; artifacts upload to the centralized registry
3. **Multi-mode inference** — in-platform UI prediction, stable REST endpoint per deployed model, ADE flow node that calls a model during pipeline execution

> **v2 corrections vs v1:** mlapp is NOT a separate HTTP service — it is an in-process FastAPI router mounted at `/mlapp_v2` in the ADE backend. All proxy-layer, `MLAPPSERVICE_URL`, and circuit-breaker references from v1 were wrong and are removed. All file paths corrected to `backend/mlapp_repo/`. Six architectural decisions flagged as blocking; Phase 0 added.

---

## Current State (Verified)

Before designing the target, anchoring to what actually exists:

| Fact | Reality |
|------|---------|
| mlapp mounting | `backend/app/api/__init__.py:22` — `api_router.include_router(mlapp, prefix="/mlapp_v2")` — **in-process router, not a separate service** |
| mlapp location | `backend/mlapp_repo/` — NOT a top-level `mlapp_repo/` |
| Training execution | `BackgroundTasks` in FastAPI event loop (`backend/mlapp_repo/service/api/models.py:179`). Training is **synchronous + CPU-bound** (`pd.read_csv`, `model.fit()`, `psutil` blocking sleeps) |
| SDK HTTP calls | `backend/mlapp_repo/mlapp/store_manament.py` — **synchronous `requests.post()` self-calls** back to the same process. No `Authorization` header — fully unauthenticated |
| Model cache | `backend/mlapp_repo/service/model_op/model_registry.py` — `TTLCache(maxsize=10, ttl=600)`. 10 min TTL, max 10 models, silent eviction |
| Training cache | `backend/mlapp_repo/service/model_op/training.py` — module-global `MODEL_CACHE: Dict[str, object]` keyed by `job_id`. **Never evicted. Lost on restart.** |
| Schema migrations | `backend/mlapp_repo/service/dbschema/table/__init__.py` — `init_tables()` calls `CREATE TABLE IF NOT EXISTS` at import. **No Alembic, no migration history, no rollback** |
| Dataset storage | `backend/mlapp_repo/service/api/datasource.py` — relative local path `mlapp_storage/datasets/{experiment_id}/{filename}`. Node-local only |
| dataset_id contract | `upload_csv` does **not** create a `datasets` DB row (returns string filename). `run_training_job` expects `dataset_service.get_dataset_by_id(id)` returning a row. **Already inconsistent** |
| Config | `backend/_config.py` — `MLAPP_*` is the **PostgreSQL connection** prefix. No `MLAPPSERVICE_URL` exists. mlapp service URL is `mlappconfig.url` (`app_env/flow_config.py:70`) — used by SDK for self-loopback |
| ADRs | Only ADR-003 exists (`.claude/adr/`). ADR-001 (Error Handling) and ADR-002 (Frontend State) referenced in roadmap but not yet written |
| Frontend nav | No ML section navigation exists. `registered-model` route orphaned — not linked from any page |

---

## System Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                        ADE Platform (Browser)                          │
│  ┌────────────┐  ┌──────────────┐  ┌────────────────┐  ┌───────────┐  │
│  │ Experiment │  │  AutoML      │  │ Model Registry │  │  Offline  │  │
│  │ Manager    │  │ Runs +       │  │ + Deployment   │  │  Import   │  │
│  │            │  │ Leaderboard  │  │                │  │           │  │
│  └────────────┘  └──────────────┘  └────────────────┘  └───────────┘  │
│                     ML Section Navigation (new sidebar/tabs)           │
└──────────────────────────────┬─────────────────────────────────────────┘
                               │ axios (withCredentials, /ade/api prefix)
                               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                ADE Backend (FastAPI, port 8000, /ade/api)               │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │   In-process mlapp router (mounted at /mlapp_v2)                │   │
│  │   /experiments  /automl  /models  /datasource                   │   │
│  │   /feature_engineering  /v1/predict  /sdk                       │   │
│  │                                                                  │   │
│  │   ┌────────────────────┐  ┌──────────────────────────────────┐  │   │
│  │   │  AutoML            │  │  Worker Pool                     │  │   │
│  │   │  Orchestrator      │──►  ProcessPoolExecutor (CPU-bound) │  │   │
│  │   │  (creates trials,  │  │  max_workers = cpu_count - 1     │  │   │
│  │   │   queues jobs)     │  │  bounded by SlotPool             │  │   │
│  │   └────────────────────┘  └──────────────────────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  ADE Flow Engine (flowcore) — ml_inference node (Phase 3)      │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└──────────────────────────────┬──────────────────────────────────────────┘
               ┌───────────────┼──────────────────┐
               ▼               ▼                  ▼
        ┌────────────┐  ┌───────────┐  ┌──────────────────┐
        │ PostgreSQL │  │ mlruns/   │  │  In-memory cache │
        │ (mlapp     │  │ (artifact │  │  (warm-up at     │
        │  schema)   │  │  pickle)  │  │   startup)       │
        └────────────┘  └───────────┘  └──────────────────┘

Data Scientist (Offline)
  └─ mlapp Python SDK ─► POST /ade/api/mlapp_v2/experiments + /runs + /metrics + /artifacts
     Bearer RS256 JWT (SDK token, 30d, issued from ADE UI)
     Calls ADE backend directly — not a self-loop
```

---

## Phase 0 — Foundations (Weeks 1–3) [NEW — REQUIRED]

These must be resolved **before any feature code is written**. They are blocking dependencies for all subsequent phases.

### 0a. ADR-004: ML Execution & Concurrency Model

**Decision required:** CPU-bound training (`model.fit()`, scikit-optimize) cannot run in the FastAPI async event loop. `asyncio.create_task` over a sync-CPU function blocks the entire ADE backend. 8 parallel trials with no bound will OOM on 100MB datasets.

**Chosen approach (to be confirmed in ADR):** `concurrent.futures.ProcessPoolExecutor`
- `max_workers = cpu_count - 1` (leaves one core for the API event loop)
- Wrap `run_training_job` with `loop.run_in_executor(pool, run_training_job, job)`
- Concurrency cap via existing `SlotPool` pattern (`backend/_lib/redis/`) — max concurrent trials = pool size
- Trial cancellation: `Future.cancel()` + `multiprocessing.Event` for mid-run abort

**Alternative (stronger):** Celery + Redis broker (Redis already in `_config.py`) — gives durable queues, restart recovery, revocation, separate worker process. Recommend for Phase 2+ if Phase 1 validates the feature.

**Restart recovery:** On ADE startup (`backend/main.py`, alongside existing Redis warmer), sweep `automl_trials` for rows in `running` state with `heartbeat_at < NOW() - 5 minutes` and mark them `failed` with reason `"server_restart"`. This unblocks the UI from polling forever.

**Heartbeat:** Each trial worker updates `automl_trials.heartbeat_at = NOW()` every 30s. The startup sweep and a background reconciliation job use this to detect orphaned trials.

**Schema addition** (to `automl_trials`):
```sql
heartbeat_at TIMESTAMP,  -- updated every 30s by trial worker
error_message TEXT        -- populated on failure, surfaced in leaderboard UI
```

### 0b. ADR-005: mlapp Deployment Topology

**Decision:** mlapp stays **in-process** (Option A) for Phases 1–3.

Consequences:
- No `mlapp_proxy.py`. No `MLAPPSERVICE_URL`.
- New AutoML routes mounted in `backend/mlapp_repo/service/api/__init__.py` under existing structure
- Frontend calls `/ade/api/mlapp_v2/automl/...` — same `axiosInstance`, same auth cookie
- Future split to standalone service is a Phase 4+ concern and needs its own ADR when scheduled

SDK loopback fix: `ParamStore.server_url` today points to `mlappconfig.url` (self). After SDK auth is added, SDK tokens are validated in-process — no network hop. The SDK on a **data scientist's laptop** posts to the ADE backend's public URL (not localhost).

### 0c. ADR-006: mlapp Schema Migration Strategy

**Decision:** Extend existing `init_tables()` pattern for Phase 0–2 (lowest risk, no tooling change). Write a formal migration plan to adopt Alembic in Phase 4 when the schema stabilizes.

Every new table must have:
1. A `classmodule.py` registered in `backend/mlapp_repo/service/dbschema/table/__init__.py`'s `init_tables()`
2. A hand-written rollback `DROP TABLE` script in `backend/mlapp_repo/service/dbschema/rollback/`

### 0d. ADR-007: SDK Authentication

**Decision:** RS256 asymmetric JWT for SDK tokens.

- **Why asymmetric:** SDK tokens are 30-day, used off-premises on laptops. The ADE signing secret must never leave the server. mlapp validates using the public key only.
- **Claims:** `sub` (ADE user_id), `scope: ["mlapp:write"]`, `iss: "ade"`, `aud: "mlapp-sdk"`, `exp` (30d), `iat`, `jti` (UUID for revocation)
- **Revocation:** Redis Set `sdk:revoked_tokens` storing `jti`. On each SDK request, check `SISMEMBER sdk:revoked_tokens {jti}`. ADE UI provides "Revoke All My SDK Tokens" action.
- **Transport:** SDK config must enforce HTTPS for `server_url`. SDK raises `InsecureConnectionError` on `http://` in production config.
- **In-process auth path:** Existing `BackgroundTasks` training calls mlapp endpoints in-process as a function call (not HTTP). These calls bypass the SDK auth middleware entirely — they go through the in-process FastAPI test client or direct function calls. Protect endpoints with: accept either ADE session cookie **OR** valid SDK Bearer token. Internal callers use a service identity token with `scope: ["mlapp:internal"]`.

### 0e. ADR-008: Dataset Storage & Access Contract

**Decision:** Shared object storage (MinIO) for datasets. `_lib/` already has a MinIO connector.

Fix the existing `upload_csv` inconsistency **in Phase 0**:
1. `upload_csv` stores to MinIO at key `datasets/{experiment_id}/{filename}`
2. Creates a `datasets` DB row: `{dataset_id (SERIAL), name, storage_key, row_count, column_count, status}`
3. Returns numeric `dataset_id` — matching what `run_training_job` and AutoML expect
4. Training workers fetch by `storage_key` from MinIO — works on any node/pod

Memory budget: one dataset loaded once per AutoML run, distributed as a reference path to workers. Each worker reads independently but from MinIO (not node-local).

### 0f. ADR-009: Inference Model Lifecycle

**Decision:** Two-tier cache with explicit warm-up.

- **Training cache** (`MODEL_CACHE` dict in `training.py`): ephemeral, fine to lose on restart, already exists
- **Serving cache** (new `ServingCache`): permanent for `is_active` deployments, no TTL eviction, sized by `SELECT COUNT(*) FROM model_deployments WHERE is_active = true`
- **Warm-up on startup** (alongside Redis warmer in `main.py`): query `model_deployments WHERE is_active AND environment = 'production'`, pre-load each model artifact from MinIO into `ServingCache`
- **Flow node timeout:** `ml_inference` node uses `timeout=30` (not 10) to accommodate occasional cache miss + MinIO fetch. Make configurable in node config form.

### 0g. Fix dataset_id inconsistency (prerequisite bug)

`upload_csv` in `backend/mlapp_repo/service/api/datasource.py` currently:
- Writes to `mlapp_storage/datasets/` (node-local) — change to MinIO
- Does NOT create a `datasets` DB row — add this
- Returns `filename` string as dataset_id — change to return `datasets.dataset_id` integer

This is a **correctness bug** that AutoML surfaces immediately. Fix before Phase 1.

### 0h. Freeze the `final_metrics` JSONB contract

Defined once in Phase 0. All training workers write this shape. All frontend visualizations read it. Retrofitting the schema later forces a data migration.

```json
{
  "train": {
    "accuracy": 0.92, "precision": 0.89, "recall": 0.87,
    "f1": 0.88, "auc": 0.94
  },
  "validation": {
    "accuracy": 0.87, "precision": 0.84, "recall": 0.82,
    "f1": 0.83, "auc": 0.91
  },
  "cv_std": {
    "accuracy": 0.02, "f1": 0.03
  },
  "training_time_seconds": 142,
  "model_size_bytes": 4200000,
  "n_train_samples": 8200,
  "n_val_samples": 1800,
  "imbalance_ratio": 0.12
}
```

Overfitting signal = `train.f1 - validation.f1`. Displayed in leaderboard. Confidence = `cv_std`.

---

## Database Schema (New Tables)

All in PostgreSQL `mlapp` schema. Registered in `init_tables()`. Rollback scripts in `backend/mlapp_repo/service/dbschema/rollback/`.

```sql
-- AutoML batch runs
CREATE TABLE IF NOT EXISTS mlapp.automl_runs (
  automl_run_id       SERIAL PRIMARY KEY,
  experiment_id       INTEGER REFERENCES mlapp.experiments(experiment_id),
  dataset_id          INTEGER REFERENCES mlapp.datasets(dataset_id),
  target_column       VARCHAR(255) NOT NULL,
  preprocessing_pipeline JSONB,
  optimization_metric VARCHAR(50)  DEFAULT 'auc',   -- default AUC, not accuracy
  models_to_try       JSONB,                        -- null = all 8 models
  time_limit_min      INTEGER DEFAULT 60,
  status              VARCHAR(50)  DEFAULT 'running', -- running|completed|cancelled|failed
  created_by          INTEGER NOT NULL,
  created_at          TIMESTAMP DEFAULT NOW(),
  completed_at        TIMESTAMP
);

-- One trial per model type per AutoML run
CREATE TABLE IF NOT EXISTS mlapp.automl_trials (
  trial_id         SERIAL PRIMARY KEY,
  automl_run_id    INTEGER REFERENCES mlapp.automl_runs(automl_run_id),
  job_id           VARCHAR(255) UNIQUE,               -- FK via job_id to model_trainings
  model_type       VARCHAR(100) NOT NULL,
  final_metrics    JSONB,                             -- shape defined in ADR-009 §0h
  rank             INTEGER,
  is_best          BOOLEAN DEFAULT FALSE,
  status           VARCHAR(50) DEFAULT 'queued',      -- queued|running|completed|failed|cancelled
  error_message    TEXT,
  heartbeat_at     TIMESTAMP,                         -- updated every 30s by worker
  created_at       TIMESTAMP DEFAULT NOW()
);

-- Stable deployed model endpoints
CREATE TABLE IF NOT EXISTS mlapp.model_deployments (
  deployment_id    SERIAL PRIMARY KEY,
  model_name       VARCHAR(255) NOT NULL,             -- matches models.model_id (VARCHAR)
  version          VARCHAR(50)  NOT NULL,
  endpoint_path    VARCHAR(500),                      -- /mlapp_v2/v1/predict/{name}/{version}
  environment      VARCHAR(50)  DEFAULT 'staging',   -- staging|production
  mlflow_stage     VARCHAR(50),                       -- mirrors VersionStage if linked
  deployed_by      INTEGER NOT NULL,
  deployed_at      TIMESTAMP DEFAULT NOW(),
  is_active        BOOLEAN DEFAULT TRUE,
  UNIQUE(model_name, version, environment)
);

-- Offline SDK model imports and bundle uploads
CREATE TABLE IF NOT EXISTS mlapp.offline_uploads (
  upload_id        SERIAL PRIMARY KEY,
  experiment_id    INTEGER REFERENCES mlapp.experiments(experiment_id),
  run_uuid         VARCHAR(255),
  upload_method    VARCHAR(50),                       -- 'sdk_direct'|'bundle_upload'
  uploaded_by      INTEGER NOT NULL,
  uploaded_at      TIMESTAMP DEFAULT NOW(),
  status           VARCHAR(50) DEFAULT 'processing',  -- processing|completed|failed
  metadata         JSONB,
  error_message    TEXT
);
```

**Rollback scripts** (`backend/mlapp_repo/service/dbschema/rollback/`):
```sql
-- rollback_automl.sql
DROP TABLE IF EXISTS mlapp.automl_trials;
DROP TABLE IF EXISTS mlapp.automl_runs;
DROP TABLE IF EXISTS mlapp.model_deployments;
DROP TABLE IF EXISTS mlapp.offline_uploads;
```

---

## AutoML Orchestrator Design

**File:** `backend/mlapp_repo/service/automl/orchestrator.py`

```python
import asyncio
from concurrent.futures import ProcessPoolExecutor
from backend._lib.redis import SlotPool  # existing pattern

_pool = ProcessPoolExecutor(max_workers=max(1, os.cpu_count() - 1))
_slot_pool = SlotPool("automl_trial", max_slots=os.cpu_count() - 1)

async def run_automl(payload: AutoMLPayload, created_by: int) -> int:
    """Non-blocking. Returns automl_run_id immediately."""
    automl_run = db.create_automl_run(payload, created_by)
    models = payload.models_to_try or ALL_MODELS

    for model_type in models:
        job = training_service.create_job(
            experiment_id=payload.experiment_id,
            dataset_id=payload.dataset_id,
            model_type=model_type,
            hyperparameters={"optimize": True},
            preprocessing_pipeline=payload.preprocessing_pipeline,
        )
        trial = db.create_trial(automl_run.automl_run_id, job.job_id, model_type)
        asyncio.create_task(_submit_trial(trial, job))

    return automl_run.automl_run_id

async def _submit_trial(trial, job):
    async with _slot_pool:          # blocks until a slot is free (caps concurrency)
        loop = asyncio.get_event_loop()
        db.update_trial_status(trial.trial_id, "running")
        try:
            await loop.run_in_executor(_pool, run_training_job, job)
            metrics = training_service.get_final_metrics(job.job_id)
            db.complete_trial(trial.trial_id, metrics)
        except Exception as e:
            db.fail_trial(trial.trial_id, str(e))
        finally:
            _maybe_finalize_automl_run(trial.automl_run_id)

def _maybe_finalize_automl_run(automl_run_id: int):
    """Rank trials and mark run complete once all trials are terminal."""
    trials = db.get_trials(automl_run_id)
    if all(t.status in ("completed", "failed", "cancelled") for t in trials):
        ranked = sorted(
            [t for t in trials if t.status == "completed"],
            key=lambda t: t.final_metrics["validation"][OPTIMIZATION_METRIC],
            reverse=True,
        )
        for i, t in enumerate(ranked):
            db.set_trial_rank(t.trial_id, rank=i + 1, is_best=(i == 0))
        status = "completed" if ranked else "failed"
        db.finalize_automl_run(automl_run_id, status)
```

**Startup reconciliation** (add to `backend/main.py` alongside `start_local_warmer()`):
```python
async def reconcile_orphaned_trials():
    stale_cutoff = datetime.utcnow() - timedelta(minutes=5)
    orphaned = db.get_trials_where(
        status="running",
        heartbeat_at_before=stale_cutoff
    )
    for trial in orphaned:
        db.fail_trial(trial.trial_id, "server_restart — no heartbeat")
```

---

## Pre-flight Validation (Phase 1, blocking)

New endpoint: `POST /mlapp_v2/automl/validate`

Called **before** the user launches an AutoML run. Prevents irreversible 2-hour failures.

```python
@router.post("/automl/validate")
async def validate_automl_config(payload: AutoMLValidatePayload):
    issues = []
    df = load_dataset_sample(payload.dataset_id, n_rows=1000)

    target = df[payload.target_column]
    if target.nunique() < 2:
        issues.append({"level": "error", "message": f"Target '{payload.target_column}' has only {target.nunique()} unique value(s). Cannot train classifier."})
    if target.isna().all():
        issues.append({"level": "error", "message": f"Target '{payload.target_column}' is all null."})
    if len(df) < 50:
        issues.append({"level": "error", "message": f"Dataset has only {len(df)} rows — minimum 50 required."})

    imbalance = target.value_counts(normalize=True).min()
    if imbalance < 0.05:
        issues.append({"level": "warning", "message": f"Target is highly imbalanced ({imbalance:.1%} minority). AUC is the recommended metric."})

    null_cols = [c for c in df.columns if df[c].isna().all()]
    if null_cols:
        issues.append({"level": "warning", "message": f"Columns with all nulls: {null_cols}. These will be dropped."})

    return {"valid": not any(i["level"] == "error" for i in issues), "issues": issues}
```

Frontend shows a "Pre-flight Check" modal before the Launch button becomes active.

---

## Complete API Contract (New Endpoints)

All paths are relative to `baseURL` (`/ade/api`). Frontend constants in `api/endpoints/automl.ts`.

### AutoML Endpoints (mounted at `/mlapp_v2/automl/`)

| Method | Path | Purpose | Auth |
|--------|------|---------|------|
| `POST` | `/mlapp_v2/automl/validate` | Pre-flight validation before launch | ADE cookie |
| `POST` | `/mlapp_v2/automl/run` | Start AutoML (all models, all HPs) | ADE cookie |
| `GET` | `/mlapp_v2/automl/runs` | List AutoML runs (filter by experiment_id) | ADE cookie |
| `GET` | `/mlapp_v2/automl/{automl_run_id}/status` | Get leaderboard + trial statuses | ADE cookie |
| `POST` | `/mlapp_v2/automl/{automl_run_id}/stop` | Cancel AutoML run + all running trials | ADE cookie |
| `POST` | `/mlapp_v2/automl/{automl_run_id}/register` | Register best (or selected) model | ADE cookie |

### Inference Endpoints (Phase 3)

| Method | Path | Purpose | Auth |
|--------|------|---------|------|
| `POST` | `/mlapp_v2/v1/predict/{model_name}/{version}` | Stable versioned prediction | ADE cookie OR SDK token |
| `GET` | `/mlapp_v2/models/deployments` | List active deployments | ADE cookie |
| `POST` | `/mlapp_v2/models/deploy` | Create deployment (enable stable endpoint) | ADE cookie, admin only |
| `DELETE` | `/mlapp_v2/models/deploy/{deployment_id}` | Deactivate deployment | ADE cookie, admin only |

### SDK Endpoints (Phase 2)

| Method | Path | Purpose | Auth |
|--------|------|---------|------|
| `POST` | `/mlapp_v2/sdk/token` | Issue RS256 SDK JWT for logged-in user | ADE cookie (required) |
| `DELETE` | `/mlapp_v2/sdk/token` | Revoke all SDK tokens for user | ADE cookie |
| `GET` | `/mlapp_v2/sdk/config` | Download `.mlapp/config.json` | ADE cookie |
| `POST` | `/mlapp_v2/sdk/ping` | Test SDK connectivity + token validity | SDK Bearer token |
| `POST` | `/mlapp_v2/sdk/upload-bundle` | Upload offline model bundle (zip) | SDK Bearer token |

### Frontend Endpoint Constants (`frontend/src/api/endpoints/automl.ts`)

```typescript
export const AUTOML_ENDPOINTS = {
  VALIDATE:    '/mlapp_v2/automl/validate',
  RUN:         '/mlapp_v2/automl/run',
  RUNS_LIST:   '/mlapp_v2/automl/runs',
  STATUS:      '/mlapp_v2/automl',           // append /{automl_run_id}/status
  STOP:        '/mlapp_v2/automl',           // append /{automl_run_id}/stop
  REGISTER:    '/mlapp_v2/automl',           // append /{automl_run_id}/register
  DEPLOYMENTS: '/mlapp_v2/models/deployments',
  DEPLOY:      '/mlapp_v2/models/deploy',
  PREDICT_V1:  '/mlapp_v2/v1/predict',       // append /{model_name}/{version}
  SDK_TOKEN:   '/mlapp_v2/sdk/token',
  SDK_PING:    '/mlapp_v2/sdk/ping',
  SDK_CONFIG:  '/mlapp_v2/sdk/config',
  SDK_UPLOAD:  '/mlapp_v2/sdk/upload-bundle',
} as const;
```

---

## User Journeys (Complete)

### Journey A: First-time user — "CSV to production"

```
1. ML section nav → "Experiments" tab
2. Add Experiment → name + description → Created
3. Click experiment → "Saved Configs" tab → [Start AutoML] button  ← (new)
4. AutoML Launch wizard:
   a. Data Source — upload CSV (fixed: creates datasets row, returns numeric dataset_id)
   b. Pre-flight Check — validates target, rows, imbalance → shows warnings/errors
   c. Feature Engineering — select target column, add preprocessing steps
   d. Model Selection — all 8 checked by default, time budget slider (30/60/120/∞)
   e. Launch → [AutoML Run Created] → redirects to Leaderboard
5. LeaderboardPage — live polling (5s), shows per-trial status chips, ETA countdown
6. On completion: "AutoML Complete — Best model: XGBoost (AUC 0.94)" banner
7. Register Best Model → Model appears in "Models" tab of ML nav
8. [Phase 3] Deploy → deployment page → copy stable endpoint URL
```

**Interim state (Phase 1–2, before Deploy exists):**
Leaderboard shows: "Model registered. Deployment endpoint available in the next release. Use the prediction form below to test now."

### Journey B: Returning data scientist — "find my AutoML run"

**This journey was missing in v1. Added as Phase 1 blocking.**

```
1. ML section nav → "AutoML Runs" tab  ← (new dedicated tab)
2. Table: Run ID | Experiment | Status | Best Model | Best AUC | Started | Actions
3. Filter by experiment / status / date range
4. Click row → LeaderboardPage (resumes polling if still running)
5. Status badge: Queued | Running (with ETA) | Completed | Failed | Cancelled
```

### Journey C: Business user — "test a registered model"

Scoped to read-only model testing. Gated by `view` role.

```
1. ML section nav → "Models" tab → registered models table
2. Click model version → Model Detail page (read-only)
3. "Test Prediction" panel — fill input fields from model schema → Submit → see result
4. Cannot Register, Deploy, or Delete (requires admin/publish role)
```

### Journey D: Admin — "org-wide model visibility"

```
1. ML section nav → "Models" tab → cross-experiment registered models (existing MlflowModelsView, now discoverable)
2. Filters: stage (None/Staging/Production/Archived), model name
3. Per-version: stage badge, "Deploy" button (admin only), deployment status badge
4. AutoML Runs across all experiments visible in "AutoML Runs" tab with experiment filter
```

---

## Frontend UI Design

### ML Section Navigation (Phase 1, blocking)

Add a sidebar or horizontal tabs to `MainPageLayout.tsx`:

```
[ Experiments ] [ AutoML Runs ] [ Models ] [ Import ] [ Docs ]
```

Routes:
| Tab | Route | Component |
|-----|-------|-----------|
| Experiments | `/model/registry/experiment` | `ExperimentsList` (existing) |
| AutoML Runs | `/model/registry/automl/runs` | `AutoMLRunsList` (new) |
| Models | `/model/registry/registered-model` | `MlflowModelsView` (existing, now linked) |
| Import | `/model/registry/import` | `ImportPage` (new, Phase 2) |
| Docs | `/model/registry/model-doc` | `ModelIntegrationDocPage` (existing) |

### New Pages

#### A. AutoML Runs List (`/model/registry/automl/runs`)
```
┌──────────────────────────────────────────────────────────────────────┐
│ AutoML Runs               [Filter: All Experiments ▼] [Status ▼]    │
├──────────────────────────────────────────────────────────────────────┤
│ ID  │ Experiment      │ Status          │ Best Model   │ AUC  │ ...  │
├─────┼─────────────────┼─────────────────┼──────────────┼──────┼──────┤
│ 42  │ Churn Q3        │ ● Running 23m   │ —            │  —   │ View │
│ 41  │ Fraud Detection │ ✓ Completed     │ XGBoost      │ 0.94 │ View │
│ 40  │ LTV Prediction  │ ✗ Failed        │ —            │  —   │ View │
└──────────────────────────────────────────────────────────────────────┘
```
`useAutoMLPoll` hook: polls `GET /mlapp_v2/automl/runs` every 10s if any row has `status = "running"`. Stops when all terminal.

#### B. AutoML Launch Wizard (`/model/registry/automl/new/:experimentId`)

3-step wizard. Step 1 reuses `data-source-selector.tsx` **with context wiring fix** (must be wrapped in `MLPlatformProvider`). The "type change" confirmation modal friction is removed — replaced with a simple "Change" button without the word-typing gate.

Step 3 additions vs existing pipeline:
- Model selection: checkboxes (all checked by default)
- Optimization metric: dropdown defaulting to **AUC** (not accuracy — see §0h warning on imbalanced banking data)
- Time budget: 30 / 60 / 120 / No limit
- **[Validate & Launch]** button → calls `POST /mlapp_v2/automl/validate` first → shows Pre-flight Check modal → on clear, calls `POST /mlapp_v2/automl/run`

#### C. AutoML Leaderboard (`/model/registry/automl/:automl_run_id`)

**All states defined:**

*State: All queued / no results yet*
```
AutoML Run #42 — Churn Q3 | ● Queued | ETA: ~45 min
[8 models queued — first results will appear as training completes]
[ XGBoost: Queued ] [ LightGBM: Queued ] [ RandomForest: Queued ] ...
```

*State: Partial results (some running, some done)*
```
AutoML Run #42 — Churn Q3 | ● Running | 3 of 8 complete | ETA: ~23 min
┌──────┬─────────────────┬──────────┬───────┬──────────────┬──────────┐
│ Rank │ Model           │ AUC (val)│ F1    │ Overfit Δ    │ Actions  │
├──────┼─────────────────┼──────────┼───────┼──────────────┼──────────┤
│  ★1  │ XGBoost ✓       │  0.941   │ 0.874 │ +0.02 ✓ low  │ Register │
│  2   │ LightGBM ✓      │  0.928   │ 0.863 │ +0.04 ✓ low  │ Register │
│      │ RandomForest ⟳  │  Running... 142s                │          │
│      │ LogisticReg ⟳  │  Running... 89s                 │          │
│      │ SVC ◷           │  Queued                         │          │
│      │ DecisionTree ✗  │  Failed — see details           │          │
└──────┴─────────────────┴──────────┴───────┴──────────────┴──────────┘
[Register Best Now] [Stop AutoML]
```

*State: Complete*
```
AutoML Complete ✓ — Best model: XGBoost (AUC 0.941) — Completed in 47 min
[Register Best Model]  [View All Results]
```

*State: All failed*
```
AutoML Run Failed — All 8 model trials encountered errors.
[View Error Details]  [Retry AutoML]
```

*Per-trial error detail (expandable row):*
```
DecisionTree — Failed
Error: Dataset has 15 features after preprocessing but model requires ≥ 20. 
      See full log ↓
```

**`LeaderboardTable` design (Phase 1, reusable for Phase 4 comparison):**
Columns: Rank | Model | AUC (val) | F1 (val) | Overfit Δ (train−val AUC) | CV Std | Train Time | Actions
Sortable by any metric column.

#### D. Model Import (`/model/registry/import`) — Phase 2

3 tabs:
1. **SDK Setup** — auto-populated code snippet using user's server URL + generated token, [Generate Token] button, [Regenerate] (revokes previous), copy button, [Download config.json], expiry countdown
2. **Bundle Upload** — drag-and-drop `.zip`, progress bar, validation feedback (missing model.pkl / invalid metadata.json), history table below
3. **Test Connection** — shows current SDK config file status, [Ping Server] button → calls `/mlapp_v2/sdk/ping` → "Connected as: Sudhakar Sinha | Token valid for: 29 days"

#### E. Model Deployment Page (`/model/registry/deploy/:modelName/:version`) — Phase 3

```
XGBoost — v1 | Status: ● Staging

Endpoint URL:  POST https://ade.wingbank.com/ade/api/mlapp_v2/v1/predict/XGBoost/1
               [Copy URL]

Example request:
  curl -X POST <url> \
    -H "Authorization: Bearer <SDK_TOKEN>" \
    -H "Content-Type: application/json" \
    -d '{"age": 35, "balance": 1200, "tenure": 5}'
  [Copy curl]   [Generated from model input schema]

Live Test:
  [age: ____] [balance: ____] [tenure: ____]
  [Predict]
  → Result: {"prediction": "churn", "probability": 0.73}

Environment:  [Staging ▼]  [Promote to Production]
Active:       [● On]
```

**Deployment vs Stage reconciliation (ADR needed before Phase 3):**
`model_deployments.environment` (staging/production) mirrors the intent of MLflow's `VersionStage`. Decision: link them — when a model is promoted to Production via the Deployment page, also update the MLflow stage to "Production" via the existing `updateModelStage` API. Single source of truth is `model_deployments`; MLflow stage is kept in sync as a label only.

### Enhancements to Existing Pages

**`ExperimentsListLogs.tsx`** — add [Start AutoML] button alongside existing [Start Training]. Both buttons visible; existing single-model path unchanged.

**`MlflowModelsView`** — add "Deploy" button per version row (admin role only), deployment badge (🔵 Staging / 🟢 Production), link to deployment page.

**`ExperimentsList.tsx`** — add "AutoML Runs" count badge per experiment row linking to filtered AutoML Runs list.

**Global nav badge** — show `N running` AutoML indicator in NavBarTop. Clicking navigates to AutoML Runs tab filtered to running. This is the **Phase 1 substitute for notifications** (email/webhook deferred to Phase 4).

---

## Shared Components Workstream (Phase 1)

Owned by frontend-dev. Build these before building pages — they are used in 3+ places:

| Component | File | Used In |
|---|---|---|
| `<JobStatusBadge status error_message>` | `FlowUIatoms/JobStatusBadge.tsx` | AutoML Runs list, Leaderboard, Logs page (fixes hardcoded `<Tag color="blue">`) |
| `useAutoMLPoll(automl_run_id)` | `mlapp/hooks/use-automl-poll.ts` | Leaderboard page, Runs list, nav badge |
| `<LeaderboardTable trials final_metrics_contract>` | `mlapp/components/LeaderboardTable.tsx` | Leaderboard, Phase 4 side-by-side compare |
| `<MetricCell value delta std tooltip>` | `mlapp/components/MetricCell.tsx` | Leaderboard table cells (AUC, overfit Δ, CV std) |
| `<CodeSnippet code language copyable>` | `FlowUIatoms/CodeSnippet.tsx` | SDK setup tab, deployment curl, integration docs |
| `<CurlCommandGenerator schema url>` | `mlapp/components/CurlCommandGenerator.tsx` | Deployment page (generates curl from model input schema) |
| `<EmptyState variant title description action>` | `FlowUIatoms/EmptyState.tsx` | All new pages + async-pending states |
| `<PreflightCheckModal issues onConfirm>` | `mlapp/components/PreflightCheckModal.tsx` | AutoML launch wizard step 3 |

---

## ADE Flow Node Integration (Phase 3)

**New module:** `backend/flowcore/internal/module/ml_inference/classmodule.py`

```python
class classmodule(basemodule):
    def validateConfig(self, data: dict) -> tuple[bool, str]:
        required = ["model_name", "model_version", "input_mapping", "output_key"]
        for key in required:
            if key not in self.config or not self.config[key]:
                return False, f"Missing required config: {key}"
        return True, "OK"

    def run(self, stack, mode, nodes, fdata):
        model_name = self.config["model_name"]
        version = self.config["model_version"]
        input_mapping = self.config["input_mapping"]   # {model_field: fdata_key}
        output_key = self.config["output_key"]
        timeout = int(self.config.get("timeout_seconds", 30))  # configurable

        row = {field: fdata.get(fdata_key) for field, fdata_key in input_mapping.items()}

        # In-process call — mlapp is an in-process router
        # Use requests to the same ADE backend via mlappconfig.url
        from app_env.flow_config import mlappconfig
        response = requests.post(
            f"{mlappconfig.url}/mlapp_v2/v1/predict/{model_name}/{version}",
            json=row,
            timeout=timeout,
            headers={"Authorization": f"Bearer {self._get_service_token()}"}
        )
        response.raise_for_status()
        fdata[output_key] = response.json()["prediction"]
        return self.returnSuccess(stack, fdata)
```

Config form fields:
- `model_name` — dropdown: `GET /mlapp_v2/models/shows`
- `model_version` — dropdown: `GET /mlapp_v2/models/versions/list?model_name=X`
- `input_mapping` — key-value editor
- `output_key` — text input
- `timeout_seconds` — number input (default 30)

---

## Offline SDK Workflow (Phase 2)

### One-time setup (data scientist)
```python
pip install mlapp  # from private PyPI or wheel built from backend/mlapp_repo/

# ADE UI → Import tab → [Generate SDK Token] → [Download config.json]
# Places file at ~/.mlapp/config.json:
# {"server_url": "https://ade.wingbank.com/ade/api", "token": "<RS256_JWT>"}

python -m mlapp.ping   # → "Connected as: Sudhakar | Token valid: 29 days"
```

### Daily training script
```python
from mlapp import mmt

with mmt.start_run(experiment_name="churn_q3_2026") as run:
    model.fit(X_train, y_train)
    run.log_metric("accuracy", 0.87)
    run.log_param("max_depth", 6)
    run.log_model(model, "churn_classifier")
    # → POST /mlapp_v2/experiments, /runs, /metrics, /artifacts
    # → Bearer RS256 token in Authorization header
```

### Alternative: bundle upload (no network during training)
```python
mlapp.export_bundle(run_id="abc123", path="./my_model_bundle.zip")
# Bundle: model.pkl, metadata.json, requirements.txt, metrics.json (final_metrics contract shape)
```
Upload via ADE UI → Import tab → Bundle Upload.

### Token lifecycle
- 30-day expiry. UI shows countdown: "Token valid for: 29 days"
- [Regenerate Token] revokes previous via Redis `jti` denylist
- Token expires → SDK raises `mlapp.exceptions.TokenExpiredError("Token expired. Generate a new one at <server_url>/ade/import")`

---

## Cross-Team Dependency Table

| Phase | Must complete first | Blocked until done | Unassigned owner |
|-------|---------------------|---------------------|-----------------|
| Phase 0 | data-engineer: `datasets` table + MinIO storage fix | All automl (dataset_id contract) | — |
| Phase 0 | data-engineer + ml-engineer: `final_metrics` JSONB shape frozen | Phase 4 viz, leaderboard display | **Assign: data-engineer owns schema, ml-engineer confirms training output** |
| Phase 1 | ml-engineer: `POST /automl/validate` + `POST /automl/run` API | frontend-dev: launch wizard | — |
| Phase 1 | ml-engineer: `GET /automl/runs` list endpoint | frontend-dev: AutoML Runs List page | **Plan v1 omitted this endpoint entirely** |
| Phase 1 | backend-dev: `created_by` propagated from ADE auth cookie into `automl_runs` | ml-engineer: orchestrator | **Auth identity injection across in-process call** |
| Phase 1 | flow-engineer: confirm orchestrator restart-recovery pattern fits `main.py` startup | ml-engineer: startup reconciliation job | **flow-engineer owns main.py startup** |
| Phase 1 | frontend-dev: shared components (`JobStatusBadge`, `useAutoMLPoll`, etc.) | All ML pages | — |
| Phase 2 | backend-dev: RS256 key pair setup + `sdk_auth.py` token issuer | ml-engineer: SDK token middleware; frontend-dev: Import tab | **Auth domain → backend-dev, not ml-engineer** |
| Phase 2 | ml-engineer: bundle format spec frozen (model.pkl + metadata.json schema) | frontend-dev: bundle upload; backend-dev: upload handler | — |
| Phase 3 | software-architect: ADR on deployment vs VersionStage reconciliation | data-engineer: `model_deployments` migration; frontend-dev: deploy page | **Conflict unresolved — needs ADR before code starts** |
| Phase 3 | ml-engineer: `/v1/predict` endpoint + deployment registry contract frozen | flow-engineer: `ml_inference` classmodule | **ml→flow contract handoff not sequenced in v1** |

---

## Phased Implementation Roadmap

### Phase 0 — Foundations (Weeks 1–3)

- [ ] Write ADR-004: ML Execution & Concurrency Model → choose ProcessPoolExecutor
- [ ] Write ADR-005: mlapp Deployment Topology → confirm in-process
- [ ] Write ADR-006: mlapp Schema Migration Strategy → extend init_tables(), plan Alembic for Phase 4
- [ ] Write ADR-007: SDK Authentication → RS256, claims, revocation
- [ ] Write ADR-008: Dataset Storage → MinIO shared storage
- [ ] Write ADR-009: Inference Model Lifecycle → two-tier cache + warm-up
- [ ] Fix `upload_csv`: MinIO storage + `datasets` DB row + numeric `dataset_id` return
- [ ] Freeze `final_metrics` JSONB contract (data-engineer + ml-engineer)
- [ ] Create rollback scripts for all 4 new tables
- [ ] Set up RS256 key pair for SDK JWT

### Phase 1 — AutoML Online Core (Weeks 4–8)

**Backend (`backend/mlapp_repo/`):**
- [ ] Create `service/automl/` module: `orchestrator.py`, `schemas.py`, `router.py`
- [ ] Create `service/dbschema/automl_runs.py` + `automl_trials.py` registered in `init_tables()`
- [ ] Implement `run_automl()` with ProcessPoolExecutor + SlotPool cap
- [ ] Implement trial heartbeat (30s updates to `heartbeat_at`)
- [ ] Add startup reconciliation sweep in `backend/main.py`
- [ ] Implement `POST /automl/validate` pre-flight endpoint
- [ ] Implement `GET /automl/runs` list endpoint (was missing in v1)
- [ ] Implement `GET /automl/{id}/status` leaderboard + ranking
- [ ] Implement `POST /automl/{id}/stop` (cancel + kill workers)
- [ ] Implement `POST /automl/{id}/register` (register selected or best model)
- [ ] Add `/automl/*` routes to `backend/mlapp_repo/service/api/__init__.py`

**Frontend:**
- [ ] Build shared components workstream first (see Shared Components table)
- [ ] Create `frontend/src/api/endpoints/automl.ts`
- [ ] Create `frontend/src/api/automl.ts` (all 6 API functions)
- [ ] Add ML section navigation to `MainPageLayout.tsx` (5 tabs)
- [ ] Build AutoML Runs List page (`/model/registry/automl/runs`)
- [ ] Build AutoML Launch wizard (`/model/registry/automl/new/:experimentId`)
  - Wire `MLPlatformProvider` context
  - Remove word-typing friction in data source change
  - Add Pre-flight Check modal
- [ ] Build AutoML Leaderboard page with all states (queued/partial/complete/failed/all-failed)
- [ ] Add [Start AutoML] button to `ExperimentsListLogs.tsx`
- [ ] Add "AutoML Runs" count badge to `ExperimentsList.tsx`
- [ ] Add global nav badge (N running AutoML indicator) to `NavBarTop`
- [ ] Add AutoML routes to `MainPage.tsx`

**Files to create/modify:**
- `backend/mlapp_repo/service/automl/` (new — 3 files)
- `backend/mlapp_repo/service/dbschema/automl_runs.py` (new)
- `backend/mlapp_repo/service/dbschema/automl_trials.py` (new)
- `backend/mlapp_repo/service/dbschema/rollback/rollback_automl.sql` (new)
- `backend/mlapp_repo/service/api/automl.py` (new router)
- `backend/main.py` (modify — add reconciliation sweep)
- `frontend/src/components/FlowUIatoms/JobStatusBadge.tsx` (new)
- `frontend/src/components/FlowUIatoms/EmptyState.tsx` (new)
- `frontend/src/components/FlowUIatoms/CodeSnippet.tsx` (new)
- `frontend/src/pages/mlapp/components/` (new directory — 4 components)
- `frontend/src/pages/mlapp/hooks/use-automl-poll.ts` (new)
- `frontend/src/pages/mlapp/automl/` (new — RunsList, LaunchPage, LeaderboardPage)
- `frontend/src/pages/mlapp/MainPage.tsx` (modify — nav + 3 new routes)
- `frontend/src/pages/mlapp/MainPageLayout.tsx` (modify — nav tabs)
- `frontend/src/pages/mlapp/ExperimentsListLogs.tsx` (modify — AutoML button)
- `frontend/src/pages/mlapp/ExperimentsList.tsx` (modify — AutoML badge)

### Phase 2 — Offline SDK Integration (Weeks 9–11)

- [ ] Set up RS256 key pair; create `backend/app/auth/sdk_jwt.py`
- [ ] Create `backend/mlapp_repo/service/api/sdk.py` router
- [ ] Implement `/sdk/token` (issue RS256 JWT), `/sdk/ping`, `/sdk/config`, `/sdk/upload-bundle`
- [ ] Implement token revocation Redis denylist middleware
- [ ] Create `backend/mlapp_repo/service/dbschema/offline_uploads.py`
- [ ] Verify `Mlapp` class reads `~/.mlapp/config.json` and sends Authorization header
- [ ] Add `mlapp ping` CLI command to SDK for connection testing
- [ ] Add `mlapp export-bundle` CLI command to SDK
- [ ] Build Model Import page: SDK Setup tab + Bundle Upload tab + Test Connection tab
- [ ] Add [Import Model] to ML section nav (was missing a direct nav entry)

### Phase 3 — Inference Layer (Weeks 12–14)

*Prerequisite: ADR on Deployment vs VersionStage reconciliation*

- [ ] Create `backend/mlapp_repo/service/dbschema/model_deployments.py`
- [ ] Implement `ServingCache` with no-TTL-eviction for active deployments
- [ ] Add startup warm-up for `is_active + environment='production'` models
- [ ] Implement `POST /mlapp_v2/v1/predict/{model_name}/{version}` stable endpoint
- [ ] Implement `/models/deploy`, `/models/deployments`, `DELETE /models/deploy/{id}`
- [ ] Sync `model_deployments.environment` → MLflow VersionStage on promote
- [ ] Create `backend/flowcore/internal/module/ml_inference/classmodule.py`
- [ ] Add ML Inference node to ADE node designer (`componentlist.tsx`)
- [ ] Build Model Deployment page (`/model/registry/deploy/:modelName/:version`)
- [ ] Add "Deploy" button + deployment badge to `MlflowModelsView`

### Phase 4 — Visualization & Polish (Weeks 15–16)

- [ ] Confusion matrix chart component
- [ ] ROC curve visualization
- [ ] Feature importance bar chart (XGBoost/LightGBM built-in)
- [ ] Side-by-side leaderboard compare (reuses `LeaderboardTable` from Phase 1)
- [ ] Email/webhook notification when AutoML run completes
- [ ] AutoML time budget enforcement (worker timeout via `multiprocessing.Event`)
- [ ] Prediction count monitoring on Deployment page
- [ ] Adopt Alembic — baseline migration stamping existing `mlapp` schema, ADR-006 Phase 2

---

## Cross-Cutting Concerns

### Authentication & Authorization

| Path | Who can call | Mechanism |
|------|-------------|-----------|
| `/mlapp_v2/automl/run` | admin, user (all base roles) | ADE session cookie |
| `/mlapp_v2/automl/{id}/stop` | run creator or admin | ADE session cookie + ownership check |
| `/mlapp_v2/models/deploy` | admin only | `Depends(require_roles(["admin"]))` |
| `/mlapp_v2/v1/predict/*` | ADE users + SDK holders | ADE cookie OR RS256 Bearer |
| `/mlapp_v2/sdk/*` (issue) | ADE users | ADE cookie (required to issue token) |
| `/mlapp_v2/sdk/ping` + `/upload-bundle` | SDK token holders | RS256 Bearer |
| In-process training calls | Service identity | Internal scope token (`mlapp:internal`) |

### Error Handling

- AutoML trial failure: mark `automl_trials.status = "failed"`, `error_message = e.message`. Continue other trials.
- All trials failed: mark `automl_runs.status = "failed"`. UI shows "All Failed" state with [Retry] button.
- Bundle upload validation failure: return 422 with structured errors (`{"field": "model.pkl", "error": "not found in zip"}`).
- Flow node prediction failure: `returnError(stack, f"ML inference failed: {e}")` — existing pattern from `basemodule`.
- SDK token expired: 401 with `{"error": "token_expired", "renew_url": "<server>/ade/import"}`.

### Polling Strategy

- Leaderboard page: every 5s while any trial `status NOT IN ('completed', 'failed', 'cancelled')`. Stop on all-terminal + show completion banner.
- AutoML Runs list: every 10s while any run `status = 'running'`. Stop when all terminal.
- Nav badge: every 30s always (low frequency global poll).
- All polling via `useAutoMLPoll` hook with exponential backoff on network errors (1→2→4→8→max 30s), stop after 5 consecutive failures.

### Real-time Updates Strategy

- Polling (above) is sufficient for 30-120 min training jobs.
- No WebSocket required for Phase 1–3.
- `VITE_WSUrl` exists if future real-time streaming of trial logs is needed (Phase 4+).

---

## Verification Plan

### Phase 0 Verification
1. `upload_csv` → verify `datasets` row created in DB, numeric `dataset_id` returned
2. Query MinIO: verify file stored at `datasets/{experiment_id}/{filename}`
3. Run `training_job` with `dataset_id` → verify it reads from MinIO path, not local

### Phase 1 Verification
1. `POST /mlapp_v2/automl/validate` with single-class target → returns `{"valid": false, "issues": [...]}`
2. `POST /mlapp_v2/automl/run` → get `automl_run_id` immediately
3. Kill the ADE process, restart → verify orphaned trials marked `failed` in DB, not `running` forever
4. Poll `GET /mlapp_v2/automl/{id}/status` → watch trials progress, verify heartbeat_at updates
5. All trials complete → verify ranks set, `is_best = true` for rank 1, `automl_runs.status = "completed"`
6. Browser: `/model/registry/automl/runs` → see run in list
7. Browser: nav badge shows "1 running"
8. Browser: launch → preflight check → leaderboard polling → completion banner

### Phase 2 Verification
1. `GET /mlapp_v2/sdk/token` (with ADE cookie) → RS256 JWT returned
2. `POST /mlapp_v2/sdk/ping` (with Bearer token) → `{"user": "Sudhakar", "valid_seconds": 2591000}`
3. `DELETE /mlapp_v2/sdk/token` → subsequent SDK call → 401 (revocation works)
4. Run SDK training script → verify experiment/run/artifacts appear in model registry
5. Export bundle → upload via UI → verify model appears in registry

### Phase 3 Verification
1. Deploy a registered model → `model_deployments` row created, `is_active = true`
2. ADE restart → verify deployed model is in `ServingCache` after warm-up
3. `POST /mlapp_v2/v1/predict/XGBoost/1 -d '{"age": 35}'` → prediction returned <30s
4. Create ADE flow with `ml_inference` node → run test mode → prediction stored in `fdata[output_key]`
5. Promote to Production → verify MLflow VersionStage = "Production" in sync

---

## Key Files Summary

| Area | File | Action |
|------|------|--------|
| Phase 0 | `backend/mlapp_repo/service/api/datasource.py` | Modify — MinIO + datasets row |
| Phase 0 | `backend/mlapp_repo/service/dbschema/rollback/rollback_automl.sql` | Create |
| Phase 1 | `backend/mlapp_repo/service/automl/orchestrator.py` | Create |
| Phase 1 | `backend/mlapp_repo/service/automl/schemas.py` | Create |
| Phase 1 | `backend/mlapp_repo/service/api/automl.py` | Create |
| Phase 1 | `backend/mlapp_repo/service/dbschema/automl_runs.py` | Create |
| Phase 1 | `backend/mlapp_repo/service/dbschema/automl_trials.py` | Create |
| Phase 1 | `backend/main.py` | Modify — startup reconciliation |
| Phase 1 | `frontend/src/components/FlowUIatoms/JobStatusBadge.tsx` | Create |
| Phase 1 | `frontend/src/components/FlowUIatoms/EmptyState.tsx` | Create |
| Phase 1 | `frontend/src/components/FlowUIatoms/CodeSnippet.tsx` | Create |
| Phase 1 | `frontend/src/pages/mlapp/components/LeaderboardTable.tsx` | Create |
| Phase 1 | `frontend/src/pages/mlapp/components/MetricCell.tsx` | Create |
| Phase 1 | `frontend/src/pages/mlapp/components/PreflightCheckModal.tsx` | Create |
| Phase 1 | `frontend/src/pages/mlapp/components/CurlCommandGenerator.tsx` | Create (Phase 3 use) |
| Phase 1 | `frontend/src/pages/mlapp/hooks/use-automl-poll.ts` | Create |
| Phase 1 | `frontend/src/api/endpoints/automl.ts` | Create |
| Phase 1 | `frontend/src/api/automl.ts` | Create |
| Phase 1 | `frontend/src/pages/mlapp/automl/RunsList.tsx` | Create |
| Phase 1 | `frontend/src/pages/mlapp/automl/LaunchPage.tsx` | Create |
| Phase 1 | `frontend/src/pages/mlapp/automl/LeaderboardPage.tsx` | Create |
| Phase 1 | `frontend/src/pages/mlapp/MainPage.tsx` | Modify — nav + 3 routes |
| Phase 1 | `frontend/src/pages/mlapp/MainPageLayout.tsx` | Modify — nav tabs |
| Phase 1 | `frontend/src/pages/mlapp/ExperimentsListLogs.tsx` | Modify — AutoML button |
| Phase 1 | `frontend/src/pages/mlapp/ExperimentsList.tsx` | Modify — AutoML badge |
| Phase 2 | `backend/app/auth/sdk_jwt.py` | Create |
| Phase 2 | `backend/mlapp_repo/service/api/sdk.py` | Create |
| Phase 2 | `backend/mlapp_repo/service/dbschema/offline_uploads.py` | Create |
| Phase 2 | `frontend/src/pages/mlapp/import/ImportPage.tsx` | Create |
| Phase 3 | `backend/mlapp_repo/service/api/inference.py` | Create |
| Phase 3 | `backend/mlapp_repo/service/dbschema/model_deployments.py` | Create |
| Phase 3 | `backend/flowcore/internal/module/ml_inference/classmodule.py` | Create |
| Phase 3 | `frontend/src/pages/mlapp/deployment/DeploymentPage.tsx` | Create |
| Phase 3 | `frontend/src/pages/mlapp/models/ml-model/mlflow-models-view.tsx` | Modify — Deploy button |

---

## ADRs to Write (Phase 0)

| ADR | Title |
|-----|-------|
| ADR-004 | ML Execution & Concurrency Model (ProcessPoolExecutor + SlotPool) |
| ADR-005 | mlapp Deployment Topology (in-process router, no proxy) |
| ADR-006 | mlapp Schema Migration Strategy (init_tables now, Alembic Phase 4) |
| ADR-007 | SDK Authentication (RS256 JWT, claims, revocation) |
| ADR-008 | Dataset Storage & Access Contract (MinIO, numeric dataset_id) |
| ADR-009 | Inference Model Lifecycle (ServingCache, startup warm-up, flow node timeout) |
| ADR-010 | Deployment vs MLflow VersionStage Reconciliation (model_deployments as source of truth) |
