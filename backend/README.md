# mfa-backend

FastAPI service for URL ingestion, job tracking, signal snapshot reads, and classification queries. This is the **HTTP entry point** for the platform.

## Purpose

The backend accepts ad-inventory URLs, normalizes them, stores crawl jobs in Postgres, and exposes APIs to poll job status, read signal snapshots, and fetch MFA classifications. It does **not** crawl pages or run ML scoring on the hot path — those run in worker containers.

## Workflow (live)

```
Client                    Backend API                 Postgres              Workers
  |  POST /api/v1/urls       |                          |                     |
  | -----------------------> |  upsert url + crawl_job  |                     |
  |  202 { job_id, ... }     | ------------------------> |                     |
  | <----------------------- |                          |  crawl_jobs queued  |
  |                          |                          | ------------------> | crawler-worker
  |                          |                          |  signal_snapshots   |
  |                          |                          |  score_jobs         |
  |                          |                          | ------------------> | ml-worker
  |                          |                          |  classifications    |
  |  GET /api/v1/jobs/{id}   |                          |                     |
  | -----------------------> |  read crawl_jobs         |                     |
  |  GET /api/v1/signals/{url_id}                       |                     |
  |  GET /api/v1/classifications/{url_id}               |                     |
  | <----------------------- |                          |                     |
```

1. **Ingest** — `POST /api/v1/urls` normalizes each URL, deduplicates via `url_hash` + `source_batch_id`, creates a `crawl_jobs` row (`status=queued`), writes `url.ingested` audit event.
2. **Poll** — `GET /api/v1/jobs/{job_id}` returns crawl job status (`queued` → `running` → `completed`/`failed`).
3. **Signals** — `GET /api/v1/signals/{url_id}` returns versioned `signal_snapshots` JSONB (written by `crawler-worker`).
4. **Classifications** — `GET /api/v1/classifications/{url_id}` returns the latest score; `/history` returns paginated past scores (written by `ml-worker`).

## API endpoints

| Method | Path | Status |
|--------|------|--------|
| `POST` | `/api/v1/urls` | Implemented |
| `GET` | `/api/v1/jobs/{job_id}` | Implemented |
| `GET` | `/api/v1/signals/{url_id}` | Implemented |
| `GET` | `/api/v1/classifications/{url_id}` | Implemented |
| `GET` | `/api/v1/classifications/{url_id}/history` | Implemented |
| `GET` | `/api/v1/jobs` (list/filter) | POC-5 |
| `POST` | `/api/v1/reviews` | MVP |
| `POST` | `/api/v1/chat` | MVP (RAG) |

OpenAPI docs: http://localhost:8000/docs

## Key packages

| Path | Role |
|------|------|
| `src/mfa/main.py` | FastAPI app, health checks |
| `src/mfa/api/v1/urls.py` | Ingestion + crawl job status |
| `src/mfa/api/v1/signals.py` | Signal snapshot reads |
| `src/mfa/api/v1/classifications.py` | Classification reads + history |
| `src/mfa/ingestion/job_poll.py` | Postgres crawl job poll (`FOR UPDATE SKIP LOCKED`) |
| `src/mfa/ingestion/score_poll.py` | Postgres score job enqueue + poll |
| `src/mfa/ingestion/service.py` | URL normalizer, idempotency, audit on ingest |
| `src/mfa/scoring/writer.py` | Persist `classifications` rows |
| `src/mfa/audit/writer.py` | Append-only `audit_events` |
| `src/mfa/schemas/signals.py` | **`SignalFeatures`**, **`SignalSnapshotPayload`** |
| `src/mfa/schemas/classifications.py` | **`ClassificationResponse`** |
| `src/mfa/db/models.py` | `Url`, `CrawlJob`, `ScoreJob`, `SignalSnapshot`, `Classification`, `AuditEvent` |
| `alembic/` | Database migrations (latest: `003_score_jobs`) |

Signal schema details: [`../docs/SIGNALS.md`](../docs/SIGNALS.md)

## Database tables

| Table | Written by | Purpose |
|-------|------------|---------|
| `urls` | Ingestion API | Normalized URL registry |
| `crawl_jobs` | Ingestion API / crawler-worker | Async crawl queue |
| `signal_snapshots` | crawler-worker | Versioned DOM signal JSONB |
| `score_jobs` | crawler-worker / ml-worker | Async score queue |
| `classifications` | ml-worker | MFA tier, score, explanation |
| `audit_events` | API + workers | Append-only audit trail |

## Run locally

### Docker (recommended)

From repo root:

```bash
docker compose up -d
docker compose --profile workers up -d
```

API docs: http://localhost:8000/docs

### Native (hot reload)

```bash
docker compose up -d postgres
uv sync --all-packages
cp backend/.env.example backend/.env
uv run --directory backend alembic upgrade head
uv run --directory backend uvicorn mfa.main:app --reload --port 8000
```

## Tests

```bash
# Unit tests
uv run --directory backend pytest tests/test_normalizer.py tests/test_signals_schema.py tests/test_classifications_schema.py -v

# Integration (requires Postgres)
MFA_RUN_INTEGRATION=1 uv run --directory backend pytest tests/test_score_poll.py tests/test_audit_writer.py tests/test_classifications_api.py tests/test_score_e2e.py -v

# All tests
MFA_RUN_INTEGRATION=1 uv run --directory backend pytest -v
```

## Environment

| Mode | Config file | `DATABASE_URL` host |
|------|-------------|---------------------|
| Docker (`docker compose up`) | Repo root `.env` | `postgres` |
| Native (`uvicorn` on host) | `backend/.env` | `localhost` |

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | Async SQLAlchemy URL (`postgresql+asyncpg://...`) |
| `DATABASE_URL_SYNC` | Alembic / sync drivers |
| `LOG_LEVEL` | `INFO`, `DEBUG`, etc. |
| `ENV` | `local` (default) |

Copy `backend/.env.example` → `backend/.env` for native dev. The Docker path uses the **root** `.env` only — see [`../README.md`](../README.md#environment-files-why-more-than-one).

## What's next

- **POC-5** — List/filter endpoints (`GET /jobs`, `GET /classifications`), OpenAPI examples
- **MVP** — Review override API (`POST /reviews`), RAG chat (`POST /chat`), Redis/SQS queue
- **MVP-4** — React review console (separate `frontend/` package)

## Related docs

- [`../README.md`](../README.md) — full stack setup
- [`../crawler/README.md`](../crawler/README.md) — Playwright crawl worker
- [`../ml/README.md`](../ml/README.md) — ML scoring worker
- [`../docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md) — system design
- [`../docs/GUARDRAILS.md`](../docs/GUARDRAILS.md) — audit and security requirements
