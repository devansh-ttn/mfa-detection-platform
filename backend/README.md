# mfa-backend

FastAPI service for URL ingestion, job tracking, and signal snapshot reads. This is the **HTTP entry point** for the platform.

## Purpose

The backend accepts ad-inventory URLs, normalizes them, stores crawl jobs in Postgres, and exposes APIs to poll job status and read signal snapshots. It does **not** crawl pages or run ML scoring on the hot path — those run in worker containers.

## Workflow (today)

```
Client                    Backend API                 Postgres
  |  POST /api/v1/urls       |                          |
  | -----------------------> |  upsert url + crawl_job  |
  |                          | ------------------------> |
  |  202 { job_id, ... }     |                          |
  | <----------------------- |                          |
  |                          |                          |
  |  GET /api/v1/jobs/{id}   |  read crawl_jobs         |
  | -----------------------> | ------------------------> |
  | <----------------------- |                          |
  |                          |                          |
  |  GET /api/v1/signals/{url_id}  (when snapshots exist)
  | -----------------------> |  read signal_snapshots   |
  | <----------------------- |                          |
```

1. **Ingest** — `POST /api/v1/urls` normalizes each URL, deduplicates via `url_hash` + `source_batch_id`, creates a `crawl_jobs` row (`status=queued`). Worker consumes via Postgres poll (`job_poll.py`).
2. **Poll** — `GET /api/v1/jobs/{job_id}` returns job status (`queued` → `running` → `completed`/`failed`).
3. **Signals** — `GET /api/v1/signals/{url_id}` returns versioned `signal_snapshots` JSONB (written by `crawler-worker` after each crawl).

## Key packages

| Path | Role |
|------|------|
| `src/mfa/main.py` | FastAPI app, health checks |
| `src/mfa/api/v1/urls.py` | Ingestion + job status |
| `src/mfa/api/v1/signals.py` | Signal snapshot reads |
| `src/mfa/ingestion/` | URL normalizer, idempotency, `job_poll.py` (Postgres worker queue) |
| `src/mfa/schemas/signals.py` | **`SignalFeatures`**, **`SignalSnapshotPayload`** — canonical signal JSON schema |
| `src/mfa/db/` | SQLAlchemy models + async session |
| `alembic/` | Database migrations |

Signal schema details: [`../docs/SIGNALS.md`](../docs/SIGNALS.md)

## Run locally

### Docker (recommended)

From repo root:

```bash
docker compose up -d
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
uv run --directory backend pytest tests/test_normalizer.py tests/test_signals_schema.py -v

# All tests (integration needs Postgres)
uv run --directory backend pytest -v

# With Postgres running
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

- ML scoring worker (`classifications` rows)
- Durable job queue (Redis/SQS) — POC-4.1
- Classifications API + audit events

## Related docs

- [`../README.md`](../README.md) — full stack setup
- [`../crawler/README.md`](../crawler/README.md) — Playwright crawl worker
- [`../docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md) — system design
