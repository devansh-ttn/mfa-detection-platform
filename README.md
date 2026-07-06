# MFA Detection Platform

AI-enabled **Made-For-Advertising (MFA)** detection platform with explainable classification, human-in-the-loop review, and a RAG conversational bot.

## Status

**Early development** — ingestion API, Playwright crawler, and signal persistence are live. ML scoring is next.

| Component | State | Details |
|-----------|--------|---------|
| `backend-api` | Live | Ingestion, jobs, signal snapshots API |
| `postgres` | Live | URLs, crawl jobs, signal/classification schema |
| `crawler-worker` | Live | Postgres job poll → crawl → `signal_snapshots` + local evidence |
| `ml-worker` | Stub | Rules + XGBoost scoring pending |

**Service guides:** [backend](backend/README.md) · [crawler](crawler/README.md) · [ml](ml/README.md) · [common](common/README.md)

Architecture: [`.cursor/plans/mfa_platform_architecture_48645023.plan.md`](.cursor/plans/mfa_platform_architecture_48645023.plan.md)  
**Build plan:** [`docs/plans/2026-07-05-phased-build-plan.md`](docs/plans/2026-07-05-phased-build-plan.md)  
Seed data: [`data/seed/`](data/seed/) — 600+ gold-labeled URLs for training.

### End-to-end flow (target)

```
POST /urls  -->  crawl job  -->  crawler (Playwright)  -->  signal_snapshots
                                                                  |
                                                           ml-worker (rules + XGBoost)
                                                                  |
                                                           classifications + audit
```

Today: ingest → `crawl_jobs` → crawler-worker → `signal_snapshots` works end-to-end. ML scoring and durable Redis/SQS queue are next milestones.

---

## Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| [Docker](https://docs.docker.com/get-docker/) | 24+ | Container runtime |
| [Docker Compose](https://docs.docker.com/compose/) | v2 (`docker compose`) | Local orchestration |

Optional (native Python dev without containerizing the API):

| Tool | Purpose |
|------|---------|
| [uv](https://docs.astral.sh/uv/) | Python package manager (workspace at repo root) |
| Python 3.12+ | Matches Docker images |

---

## Environment files (why more than one?)

We do **not** duplicate config for every service. There are two roles:

| File | When you need it | Why it exists |
|------|------------------|---------------|
| **`.env`** (repo root) | `docker compose up` | Compose loads `./.env` automatically and injects vars into containers. DB host is `postgres` (Docker network). |
| **`backend/.env`** | Native API on the host (`uvicorn` outside Docker) | Pydantic settings load `backend/.env` when cwd is `backend/`. DB host is `localhost` (published port). |
| **`crawler/.env`** | Optional | Crawler-only settings (`CRAWL_*`). Smoke CLI reads `os.getenv`; Compose still uses root `.env` for workers. |

**Rule of thumb**

- **Everything in Docker** → only copy `cp .env.example .env` at the repo root.
- **API on host + Postgres in Docker** → also `cp backend/.env.example backend/.env`.
- **Custom crawl settings locally** → optionally `cp crawler/.env.example crawler/.env`.

`ml-worker` has no separate `.env` yet; it only needs `ENV`, `LOG_LEVEL`, and `DATABASE_URL` from Compose today.

Do not commit `.env` files (gitignored). Commit `.env.example` templates only.

---

## Run locally with Docker Compose

All commands below are run from the **repository root** (`mfa-detection-platform/`).

### 1. Clone and configure environment

```bash
git clone <repo-url> mfa-detection-platform
cd mfa-detection-platform
cp .env.example .env
```

The root `.env` is read by Compose only. Defaults work for local development; edit if you change Postgres credentials or ports.

For native backend dev on the host, also see [Environment files](#environment-files-why-more-than-one) and `backend/.env.example`.

| Variable | Default (Docker) | Notes |
|----------|------------------|-------|
| `POSTGRES_USER` / `PASSWORD` / `DB` | `mfa` / `mfa` / `mfa` | Postgres container |
| `DATABASE_URL` | `...@postgres:5432/mfa` | Hostname `postgres` = Compose service name |
| `DATABASE_URL_SYNC` | `...@postgres:5432/mfa` | Used by Alembic on API startup |
| `LOG_LEVEL` | `INFO` | JSON structured logs |
| `ENV` | `local` | App environment label |

### 2. Build and start core services

Starts **Postgres** and the **backend API**. The API container runs Alembic migrations automatically on startup, then serves FastAPI on port 8000.

```bash
docker compose build
docker compose up -d
```

Check status:

```bash
docker compose ps
```

Expected: `mfa-postgres` (healthy), `mfa-backend-api` (running).

### 3. Verify the stack

```bash
# API liveness
curl -s http://localhost:8000/health | jq

# Database connectivity
curl -s http://localhost:8000/health/db | jq
```

Open interactive API docs: **http://localhost:8000/docs**

### 4. Submit URLs (ingestion smoke test)

```bash
curl -s -X POST http://localhost:8000/api/v1/urls \
  -H "Content-Type: application/json" \
  -d '{
    "urls": ["https://example.com/article"],
    "source_batch_id": "local-smoke-test",
    "priority": 1
  }' | jq
```

Response is `202 Accepted` with `job_id` values. Poll a job:

```bash
# Replace JOB_ID from the response above
curl -s http://localhost:8000/api/v1/jobs/JOB_ID | jq
```

Jobs are stored in Postgres (`crawl_jobs.status=queued`). Start `crawler-worker` to process them:

```bash
docker compose --profile workers up -d crawler-worker
docker compose logs -f crawler-worker
```

Poll job status via `GET /api/v1/jobs/{job_id}` until `status` is `completed`.

### 5. Crawl smoke test (Playwright)

The crawler can extract DOM metrics without the API. See [`crawler/README.md`](crawler/README.md) for full detail.

**Native:**

```bash
uv sync --all-packages
uv run --package mfa-crawler playwright install chromium
uv run --package mfa-crawler python -m mfa_crawler.smoke
```

**Docker:**

```bash
docker compose --profile workers build crawler-worker
docker compose --profile workers run --rm crawler-worker \
  uv run --package mfa-crawler python -m mfa_crawler.smoke
```

Prints a `SignalSnapshotPayload` JSON document (`schema_version: v1`) with five core DOM metrics.

### 6. Optional — start worker containers

```bash
docker compose --profile workers up -d
```

| Worker | Current behavior |
|--------|------------------|
| `crawler-worker` | Polls Postgres for queued jobs; crawls, persists snapshots + evidence artifacts |
| `ml-worker` | Heartbeat stub until scoring pipeline ships |

```bash
docker compose logs -f crawler-worker ml-worker
```

---

## Compose services reference

| Service | Container | Port | Dockerfile | Profile | README |
|---------|-----------|------|------------|---------|--------|
| `postgres` | `mfa-postgres` | 5432 | Official `postgres:16-alpine` | default | — |
| `backend-api` | `mfa-backend-api` | 8000 | `backend/Dockerfile` | default | [backend/README.md](backend/README.md) |
| `crawler-worker` | `mfa-crawler-worker` | — | `crawler/Dockerfile` | `workers` | [crawler/README.md](crawler/README.md) |
| `ml-worker` | `mfa-ml-worker` | — | `ml/Dockerfile` | `workers` | [ml/README.md](ml/README.md) |

Python dependencies are installed with **uv** inside each image. The monorepo uses a single `uv.lock` at the repo root. Shared logging lives in [common/README.md](common/README.md).

---

## Day-to-day Docker commands

```bash
# Follow API logs
docker compose logs -f backend-api

# Rebuild after code changes
docker compose build backend-api
docker compose up -d backend-api

# Stop everything (keep database volume)
docker compose down

# Stop and remove database volume (fresh DB)
docker compose down -v

# Full rebuild from scratch
docker compose build --no-cache
docker compose up -d
```

---

## Troubleshooting

**Port 5432 already in use**  
Another Postgres instance is bound to 5432. Stop it or change the host port in `docker-compose.yml` (e.g. `"5433:5432"`) and update `DATABASE_URL` in `.env` if connecting from the host.

**Container name conflict (`mfa-postgres`)**  
A leftover container from an older setup may exist:

```bash
docker rm -f mfa-postgres mfa-backend-api
docker compose up -d
```

**API exits on startup / migration errors**  
Check logs: `docker compose logs backend-api`. Ensure `DATABASE_URL_SYNC` uses hostname `postgres` (not `localhost`) when running inside Compose.

**`curl: connection refused` on :8000**  
Wait for Postgres healthcheck and migration: `docker compose logs -f backend-api` until you see the uvicorn startup line.

**Playwright / Chromium errors (crawler)**  
Run `uv run --package mfa-crawler playwright install chromium` on the host, or rebuild the `crawler-worker` image. See [crawler/README.md](crawler/README.md).

---

## Native development (API on host, Postgres in Docker)

Use this when you want hot reload without rebuilding the API image.

```bash
# 1. Postgres only
docker compose up -d postgres

# 2. Python workspace (repo root)
uv sync --all-packages

# 3. Backend env — localhost, not "postgres"
cp backend/.env.example backend/.env

# 4. Migrations + dev server
uv run --directory backend alembic upgrade head
uv run --directory backend uvicorn mfa.main:app --reload --port 8000
```

API: http://localhost:8000/docs

### Tests

```bash
# Backend unit tests
uv run --directory backend pytest tests/test_normalizer.py tests/test_signals_schema.py -v

# Backend integration (requires Postgres on localhost:5432)
MFA_RUN_INTEGRATION=1 uv run --directory backend pytest -v

# Crawler unit tests
uv run --directory crawler pytest -m "not integration" -v

# Crawler browser integration
PLAYWRIGHT_SMOKE=1 uv run --directory crawler pytest -m integration -v

# Gold-label seed validation
python scripts/seed/validate_gold_labels.py
```

---

## Repository layout

```
mfa-detection-platform/
├── docker-compose.yml      # Local orchestration (root level)
├── pyproject.toml          # uv workspace root
├── uv.lock
├── .env.example            # Docker Compose env (repo root)
├── common/                 # mfa-common — shared logging          → common/README.md
├── backend/                # FastAPI ingestion API                  → backend/README.md
│   └── .env.example        # Native host dev only (localhost DB)
├── crawler/                # Playwright crawl worker                → crawler/README.md
│   └── .env.example        # Optional CRAWL_* overrides (native)
├── ml/                     # Rules + XGBoost scoring                → ml/README.md
├── data/seed/              # Gold-label training URLs
└── docs/                   # Architecture, ADRs, roadmap, signals
```

Details: [`AGENTS.md`](AGENTS.md)

---

## For Cursor AI

| Resource | Purpose |
|----------|---------|
| [`AGENTS.md`](AGENTS.md) | Agent entry point — mission, stack, workflow |
| [`docs/`](docs/) | Architecture, domain, ADRs, signals, RAG, roadmap, guardrails |
| [`.cursor/rules/`](.cursor/rules/) | Layer-specific rules (core, security, ML, RAG, crawler, API, infra, UI) |
| [`.cursor/skills/`](.cursor/skills/) | Workflow skills (platform, signals, classifier, crawler, RAG, ADR) |
| [`.cursor/agents/`](.cursor/agents/) | Specialized subagents (architect, ML, RAG, crawler, security, UI) |

---

## Roadmap milestones

Planning scope only — implementation uses production-oriented names (`SignalFeatures`, `v1`). See [`AGENTS.md`](AGENTS.md).

| Milestone | Focus |
|-----------|-------|
| **Baseline** (6–8 wk) | Rules + XGBoost, single-persona crawl, Postgres, template explanations |
| **MVP** (+10–12 wk) | Dual-persona, LLM explanations, RAG v1, review console, OpenSearch |
| **Production** (+12–16 wk) | Near-real-time, pre-bid API, auto-retrain, SSO, multi-region |

Details: [`docs/ROADMAP.md`](docs/ROADMAP.md)

## Core design principles

1. **Hybrid ML + LLM** — rules + XGBoost classify; LLM explains and powers RAG only
2. **Page-section granularity** — score URL paths, not domains alone
3. **Versioned evidence** — immutable signal snapshots for audit and RAG grounding
4. **Retrieve-first RAG** — citation validator on every answer

## License

Internal assessment project.
