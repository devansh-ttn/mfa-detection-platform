# MFA Detection Platform

AI-enabled **Made-For-Advertising (MFA)** detection platform with explainable classification, human-in-the-loop review, and a RAG conversational bot.

## Status

**Baseline — POC-4 complete.** Ingestion, crawl, ML scoring, and classifications API are wired end-to-end via async workers.

| Component | State | Details |
|-----------|--------|---------|
| `backend-api` | Live | Ingestion, jobs, signals, classifications API, audit writer |
| `postgres` | Live | URLs, crawl jobs, score jobs, signal snapshots, classifications, audit events |
| `crawler-worker` | Live | Postgres poll → crawl → `signal_snapshots` → enqueue `score_jobs` |
| `ml-worker` | Live | Postgres poll → `classify_snapshot()` → `classifications` + audit |

**Service guides:** [backend](backend/README.md) · [crawler](crawler/README.md) · [ml](ml/README.md) · [common](common/README.md)

Architecture: [`.cursor/plans/mfa_platform_architecture_48645023.plan.md`](.cursor/plans/mfa_platform_architecture_48645023.plan.md)  
**Build plan:** [`docs/plans/2026-07-05-phased-build-plan.md`](docs/plans/2026-07-05-phased-build-plan.md)  
**Baseline completion:** [`docs/plans/2026-07-06-baseline-completion.md`](docs/plans/2026-07-06-baseline-completion.md)  
Seed data: [`data/seed/`](data/seed/) — 600+ gold-labeled URLs for training.

### End-to-end flow (live)

```
POST /urls  -->  crawl_jobs  -->  crawler-worker  -->  signal_snapshots
                                                              |
                                                       score_jobs (queued)
                                                              |
                                                       ml-worker (rules + XGBoost)
                                                              |
                                              classifications + audit_events
                                                              |
                                              GET /classifications/{url_id}
```

**Next milestone (POC-5):** List/filter APIs, batch eval report, reviewer CSV export, demo script.  
**Frontend:** MVP only — review console starts at MVP-4.1 (see [Roadmap](#roadmap-milestones)).

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

| Variable | Default (Docker) | Notes |
|----------|------------------|-------|
| `POSTGRES_USER` / `PASSWORD` / `DB` | `mfa` / `mfa` / `mfa` | Postgres container |
| `DATABASE_URL` | `...@postgres:5432/mfa` | Hostname `postgres` = Compose service name |
| `DATABASE_URL_SYNC` | `...@postgres:5432/mfa` | Used by Alembic on API startup |
| `LOG_LEVEL` | `INFO` | JSON structured logs |
| `ENV` | `local` | App environment label |
| `ARTIFACT_DIR` | `/artifacts` (ml-worker) | Mounted from `./ml/artifacts/v1` |
| `SCORE_POLL_INTERVAL_SEC` | `5` | ML worker idle poll interval |

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
curl -s http://localhost:8000/health | jq
curl -s http://localhost:8000/health/db | jq
```

Open interactive API docs: **http://localhost:8000/docs**

### 4. Start workers (crawl + score)

```bash
docker compose --profile workers up -d --build
docker compose --profile workers ps
```

Expected: `mfa-crawler-worker` and `mfa-ml-worker` running. The ML worker requires trained artifacts in `ml/artifacts/v1/` (mounted read-only at `/artifacts`).

### 5. Full E2E smoke test (ingest → crawl → score → classification)

```bash
# Submit URL
RESP=$(curl -s -X POST http://localhost:8000/api/v1/urls \
  -H "Content-Type: application/json" \
  -d '{"urls": ["https://example.com"], "source_batch_id": "local-smoke-test"}')

echo "$RESP" | jq
JOB_ID=$(echo "$RESP" | jq -r '.jobs[0].job_id')
URL_ID=$(echo "$RESP" | jq -r '.jobs[0].url_id')

# Poll crawl job
until [ "$(curl -s http://localhost:8000/api/v1/jobs/${JOB_ID} | jq -r .status)" = "completed" ]; do
  echo "crawl: waiting..."; sleep 3
done

# Poll classification (score is async)
until curl -sf "http://localhost:8000/api/v1/classifications/${URL_ID}" > /dev/null 2>&1; do
  echo "score: waiting..."; sleep 3
done

curl -s "http://localhost:8000/api/v1/classifications/${URL_ID}" | jq
```

**Expect:** `tier`, `mfa_score`, `confidence`, `top_signals`, `explanation`, `evidence_hash`, `classifier`, `schema_version`.

### 6. Read signals and classification history

```bash
curl -s "http://localhost:8000/api/v1/signals/${URL_ID}" | jq
curl -s "http://localhost:8000/api/v1/classifications/${URL_ID}/history" | jq
```

### 7. Verify audit trail (optional)

```bash
docker exec -it mfa-postgres psql -U mfa -d mfa \
  -c "SELECT action, entity_type, evidence_hash FROM audit_events ORDER BY occurred_at DESC LIMIT 10;"
```

**Expect actions:** `url.ingested`, `crawl.completed`, `classification.scored`.

---

## API endpoints (implemented)

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/health`, `/health/db` | Liveness and DB connectivity |
| `POST` | `/api/v1/urls` | Submit URL(s) for crawl + score |
| `GET` | `/api/v1/jobs/{job_id}` | Crawl job status |
| `GET` | `/api/v1/signals/{url_id}` | Versioned signal snapshots |
| `GET` | `/api/v1/classifications/{url_id}` | Latest classification |
| `GET` | `/api/v1/classifications/{url_id}/history` | Paginated classification history |

Planned (POC-5 / MVP): list/filter endpoints, review overrides, RAG chat.

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
# Follow worker logs
docker compose logs -f crawler-worker ml-worker

# Rebuild after code changes
docker compose build backend-api
docker compose --profile workers build ml-worker crawler-worker
docker compose --profile workers up -d

# Stop everything (keep database volume)
docker compose down

# Stop and remove database volume (fresh DB)
docker compose down -v
```

---

## Troubleshooting

**Port 5432 already in use**  
Stop the other Postgres instance or change the host port in `docker-compose.yml`.

**No classification after crawl completes**  
Check `docker logs mfa-ml-worker`. Ensure `ml/artifacts/v1/` contains `model.pkl`, `calibrator.pkl`, and `metadata.json`.

**Score job stuck**  
```bash
docker exec -it mfa-postgres psql -U mfa -d mfa \
  -c "SELECT id, status, error_message FROM score_jobs ORDER BY created_at DESC LIMIT 5;"
```

**API exits on startup / migration errors**  
`docker compose logs backend-api` — run `uv run --directory backend alembic upgrade head` if needed.

**Playwright / Chromium errors (crawler)**  
Rebuild `crawler-worker` or run `uv run --package mfa-crawler playwright install chromium`. See [crawler/README.md](crawler/README.md).

---

## Native development (API on host, Postgres in Docker)

```bash
docker compose up -d postgres
uv sync --all-packages
cp backend/.env.example backend/.env
uv run --directory backend alembic upgrade head
uv run --directory backend uvicorn mfa.main:app --reload --port 8000
```

Workers on host (separate terminals):

```bash
export DATABASE_URL=postgresql+asyncpg://mfa:mfa@localhost:5432/mfa
export ARTIFACT_DIR=ml/artifacts/v1
uv run --package mfa-crawler python -m mfa_crawler.worker
uv run --package mfa-ml python -m mfa_ml.worker
```

### Tests

```bash
# Unit tests (no Postgres)
uv run --package mfa-backend pytest backend/tests/test_normalizer.py backend/tests/test_signals_schema.py -v
uv run --package mfa-ml pytest ml/tests/ -q --ignore=ml/tests/test_consumer.py
uv run --package mfa-crawler pytest crawler/tests/ -m "not integration" -v

# Integration tests (Postgres on localhost:5432)
MFA_RUN_INTEGRATION=1 uv run --package mfa-backend pytest backend/tests/ -v
MFA_RUN_INTEGRATION=1 uv run --package mfa-crawler pytest crawler/tests/ -v
MFA_RUN_INTEGRATION=1 uv run --package mfa-ml pytest ml/tests/test_consumer.py -v

# Gold-label seed validation
python scripts/seed/validate_gold_labels.py
```

### ML evaluation (offline)

```bash
uv run --package mfa-ml python ml/scripts/evaluate.py \
  --db-url postgresql://mfa:mfa@localhost:5432/mfa \
  --gold-labels data/seed/gold_labels.jsonl \
  --artifact-dir ml/artifacts/v1
```

Results: `ml/artifacts/v1/metrics.json`. See `ml/artifacts/v1/eval_notes.md` for pass/fail vs 85%/70% targets.

---

## Repository layout

```
mfa-detection-platform/
├── docker-compose.yml      # Local orchestration (root level)
├── pyproject.toml          # uv workspace root
├── uv.lock
├── .env.example            # Docker Compose env (repo root)
├── common/                 # mfa-common — shared logging          → common/README.md
├── backend/                # FastAPI ingestion + classifications API → backend/README.md
├── crawler/                # Playwright crawl worker                → crawler/README.md
├── ml/                     # Rules + XGBoost scoring + ml-worker    → ml/README.md
├── data/seed/              # Gold-label training URLs
└── docs/                   # Architecture, ADRs, roadmap, signals
```

Details: [`AGENTS.md`](AGENTS.md) · Full local guide: [`docs/LOCAL_DEV_GUIDE.md`](docs/LOCAL_DEV_GUIDE.md)

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

| Milestone | Focus | Frontend |
|-----------|-------|----------|
| **Baseline** (6–8 wk) | Rules + XGBoost, single-persona crawl, Postgres, template explanations | Spreadsheet / CSV export (POC-5.5) |
| **MVP** (+10–12 wk) | Dual-persona, LLM explanations, RAG v1, review console, OpenSearch | **MVP-4.1** — Vite + React + TypeScript review UI |
| **Production** (+12–16 wk) | Near-real-time, pre-bid API, auto-retrain, SSO, multi-region | SSO, multi-tenant hardening |

Details: [`docs/ROADMAP.md`](docs/ROADMAP.md)

## Core design principles

1. **Hybrid ML + LLM** — rules + XGBoost classify; LLM explains and powers RAG only
2. **Page-section granularity** — score URL paths, not domains alone
3. **Versioned evidence** — immutable signal snapshots for audit and RAG grounding
4. **Retrieve-first RAG** — citation validator on every answer

## License

Internal assessment project.
