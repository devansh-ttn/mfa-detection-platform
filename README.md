# MFA Detection Platform

AI-enabled **Made-For-Advertising (MFA)** detection platform with explainable classification, human-in-the-loop review, and a RAG conversational bot.

## Status

**POC in progress** — backend ingestion API is bootstrapped (URL submit, crawl jobs, Postgres). Crawler and ML workers run as **stubs** until Phase 2/3.

| Component | State |
|-----------|--------|
| `backend-api` | FastAPI — `POST /api/v1/urls`, `GET /api/v1/jobs/{id}` |
| `postgres` | PostgreSQL 16 — URLs, crawl jobs, schema for signals/classifications |
| `crawler-worker` | Stub consumer (Playwright crawl in Phase 3) |
| `ml-worker` | Stub consumer (rules + XGBoost in Phase 2) |

Architecture: [`.cursor/plans/mfa_platform_architecture_48645023.plan.md`](.cursor/plans/mfa_platform_architecture_48645023.plan.md)  
**Build plan:** [`docs/plans/2026-07-05-phased-build-plan.md`](docs/plans/2026-07-05-phased-build-plan.md) — POC → MVP → Production tasks  
Seed data: [`data/seed/`](data/seed/) — 600+ gold-labeled URLs for POC training.

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

## Run locally with Docker Compose

All commands below are run from the **repository root** (`mfa-detection-platform/`).

### 1. Clone and configure environment

```bash
git clone <repo-url> mfa-detection-platform
cd mfa-detection-platform
cp .env.example .env
```

The root `.env` file is read by Compose. Defaults work for local POC; edit only if you change Postgres credentials or ports.

| Variable | Default (Docker) | Notes |
|----------|------------------|-------|
| `POSTGRES_USER` / `PASSWORD` / `DB` | `mfa` / `mfa` / `mfa` | Postgres container |
| `DATABASE_URL` | `...@postgres:5432/mfa` | Hostname `postgres` = Compose service name |
| `DATABASE_URL_SYNC` | `...@postgres:5432/mfa` | Used by Alembic on API startup |
| `LOG_LEVEL` | `INFO` | JSON structured logs |

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

Jobs are enqueued in-memory inside the API process for POC; worker containers will consume from a real queue in later phases.

### 5. Optional — start worker stubs

Crawler and ML images are POC placeholders. They use the `workers` Compose profile:

```bash
docker compose --profile workers up -d
```

View worker logs (JSON):

```bash
docker compose logs -f crawler-worker ml-worker
```

---

## Compose services reference

| Service | Container | Port | Dockerfile | Profile |
|---------|-----------|------|------------|---------|
| `postgres` | `mfa-postgres` | 5432 | Official `postgres:16-alpine` | default |
| `backend-api` | `mfa-backend-api` | 8000 | `backend/Dockerfile` | default |
| `crawler-worker` | `mfa-crawler-worker` | — | `crawler/Dockerfile` | `workers` |
| `ml-worker` | `mfa-ml-worker` | — | `ml/Dockerfile` | `workers` |

Python dependencies are installed with **uv** inside each image. The monorepo uses a single `uv.lock` at the repo root.

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
# Unit tests (no database)
uv run --directory backend pytest tests/test_normalizer.py -v

# Integration tests (requires Postgres on localhost:5432)
MFA_RUN_INTEGRATION=1 uv run --directory backend pytest -v
```

---

## Repository layout

```
mfa-detection-platform/
├── docker-compose.yml      # Local orchestration (root level)
├── pyproject.toml          # uv workspace root
├── uv.lock
├── .env.example            # Docker Compose env
├── common/                 # mfa-common (shared logging)
├── backend/                # FastAPI ingestion API
├── crawler/                # Playwright crawl worker
├── ml/                     # Rules + XGBoost scoring
├── data/seed/              # Gold-label training URLs
└── docs/                   # Architecture, ADRs, roadmap
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

## Roadmap phases

| Phase | Focus |
|-------|-------|
| **POC** (6–8 wk) | Rules + XGBoost, single-persona crawl, Postgres, template explanations |
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
