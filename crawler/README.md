# mfa-crawler

Playwright-based headless crawler that visits ad-inventory URLs and extracts DOM metrics into **`SignalSnapshotPayload`** documents.

## Purpose

MFA detection needs **page-level evidence** — ad density, content quality, layout signals — not just a domain name. The crawler loads each URL in Chromium, runs DOM heuristics, and produces a validated signal payload the ML pipeline can score.

The long-running **`crawler-worker`** polls Postgres for `crawl_jobs` with `status=queued`, crawls each URL, persists `signal_snapshots`, enqueues a `score_jobs` row, writes local evidence artifacts, and updates job status to `completed` or `failed`.

## Workflow

```
ingest API  -->  crawl_jobs (queued)  -->  worker.py / consumer.py
                                              |
                    browser.py --> dom_parser.py --> crawl.py
                                              |
                         persist.py --> signal_snapshots + evidence_hash
                         artifacts.py --> backend/evidence/{url_id}/{version}/
                                              |
                         enqueue_score_job() --> score_jobs (queued)
                                              |
                                         ml-worker scores
```

1. **`browser.py`** — Launches Chromium, navigates to the URL (`persona=direct` only for now).
2. **`dom_parser.py`** — Injects JavaScript via `page.evaluate()` to measure ad slots, above-fold ads, sticky ads, content word count, and ad-to-content ratio.
3. **`crawl.py`** — Orchestrates the crawl; captures HTML + screenshot; returns `CrawlResult`.
4. **`persist.py`** — Inserts a versioned `signal_snapshots` row with `evidence_hash` (`persona=direct`).
5. **`artifacts.py`** — Writes `screenshot.png`, `page.html`, `dom_metrics.json` per url_id/version.
6. **`consumer.py`** — Claims queued jobs, runs `crawl_and_persist`, enqueues `score_jobs`, writes `crawl.completed` audit event.
7. **`errors.py`** — Typed crawl errors (`not_found`, `timeout`, etc.) with permanent/transient classification.
8. **`smoke.py`** — CLI to test a single URL (print JSON or `--persist` to Postgres).

Unimplemented features (refresh dwell, native ads, etc.) are stored as `null` per [`../docs/SIGNALS.md`](../docs/SIGNALS.md).

## Core metrics (current)

| Field | Description |
|-------|-------------|
| `ad_slots_count` | Visible ad-like elements (iframes, ad slots, etc.) |
| `ads_above_fold` | Ad elements visible without scrolling |
| `sticky_ad_count` | Ads with `position: fixed` or `sticky` |
| `content_word_count` | Words in `article` / `main` / `body` text |
| `ad_to_content_ratio` | Approximate ad area ÷ content area (0–1) |

Output is wrapped in `SignalSnapshotPayload` with `schema_version: "v1"` and imported from `mfa.schemas.signals` (backend package).

## Run locally

### One-time: install Chromium

```bash
uv sync --all-packages
uv run --package mfa-crawler playwright install chromium
```

### Smoke crawl

```bash
# Default: https://example.com
uv run --package mfa-crawler python -m mfa_crawler.smoke

# Custom URL
uv run --package mfa-crawler python -m mfa_crawler.smoke https://example.com/article

# Persist to Postgres (url must exist from ingestion API)
uv run --package mfa-crawler python -m mfa_crawler.smoke --persist --url-id <UUID>
```

### Docker

```bash
docker compose --profile workers build crawler-worker
docker compose --profile workers run --rm crawler-worker \
  uv run --package mfa-crawler python -m mfa_crawler.smoke
```

### Worker (queue consumer)

```bash
# Start full stack + workers
docker compose up -d
docker compose --profile workers up -d

# Ingest URLs (creates crawl_jobs with status=queued)
curl -s -X POST http://localhost:8000/api/v1/urls \
  -H 'Content-Type: application/json' \
  -d '{"urls": ["https://example.com"]}'

# Watch worker process jobs
docker compose logs -f crawler-worker

# Evidence artifacts on host
ls backend/evidence/<url_id>/1/

# Verify score job was enqueued
docker exec -it mfa-postgres psql -U mfa -d mfa \
  -c "SELECT id, status FROM score_jobs ORDER BY created_at DESC LIMIT 5;"
```

Native worker (Postgres must be running; set `DATABASE_URL`):

```bash
export DATABASE_URL=postgresql+asyncpg://mfa:mfa@localhost:5432/mfa
uv run --package mfa-crawler python -m mfa_crawler.worker
```

## Tests

```bash
# Unit tests (no browser, no Postgres)
uv run --directory crawler pytest -m "not integration" -v

# Postgres integration (persist, consumer, job poll, score enqueue)
MFA_RUN_INTEGRATION=1 uv run --directory crawler pytest -v

# Browser integration (requires Chromium installed)
PLAYWRIGHT_SMOKE=1 uv run --directory crawler pytest -m integration -v
```

## Configuration

| Variable | Default | Purpose |
|----------|---------|---------|
| `CRAWL_HEADLESS` | `true` | Run Chromium headless |
| `CRAWL_TIMEOUT_MS` | `30000` | Navigation timeout |
| `CRAWL_USER_AGENT` | `MFA-Detection-Crawler/0.1 (...)` | Identifiable user-agent |
| `LOG_LEVEL` | `INFO` | JSON structured logs |
| `ENV` | `local` | Environment label in logs |
| `DATABASE_URL` | (see root `.env`) | Required for worker / `--persist`; async Postgres URL |
| `EVIDENCE_DIR` | `backend/evidence` | Root path for screenshot/HTML/dom_metrics artifacts |
| `CRAWL_POLL_INTERVAL_SEC` | `5` | Worker idle poll interval when queue is empty |

Optional: `cp crawler/.env.example crawler/.env` for local smoke runs. Docker workers get vars from the **repo root** `.env` via Compose.

## Module map

| File | Role |
|------|------|
| `browser.py` | Playwright lifecycle, navigation, typed error mapping |
| `dom_parser.py` | `extract_dom_metrics(page) -> SignalFeatures` |
| `crawl.py` | `crawl_url(url) -> CrawlResult` (payload + HTML + screenshot) |
| `artifacts.py` | `write_evidence_artifacts()` to `{url_id}/{version}/` |
| `persist.py` | `crawl_and_persist(url_id)` + `persist_signal_snapshot()` |
| `errors.py` | `CrawlError` hierarchy, permanent vs transient types |
| `consumer.py` | Postgres job poll, crawl, score job enqueue, audit |
| `smoke.py` | CLI entrypoint (`--persist --url-id`) |
| `worker.py` | Long-running queue consumer entrypoint |
| `spike.py` / `spike_cli.py` | 100-domain crawl spike + report (POC-2.5) |

## What's next

- **POC-5** — Batch eval on full gold-label set
- **TODO(MVP):** Dual-persona crawl, 60s refresh dwell, S3 artifacts, Redis/SQS queue

## Crawler spike (POC-2.5)

Evaluate crawl success and DOM metrics on seed domains:

```bash
uv run --package mfa-crawler python -m mfa_crawler.spike_cli
uv run --package mfa-crawler python -m mfa_crawler.spike_cli --domains 10 --delay-sec 0
```

Writes `crawler/artifacts/crawl_spike/report.json` and `report.md`. Baseline 100-domain report is committed under `crawler/artifacts/crawl_spike/`.

## Related docs

- [`../docs/SIGNALS.md`](../docs/SIGNALS.md) — feature schema
- [`../backend/README.md`](../backend/README.md) — ingestion API + classifications
- [`../ml/README.md`](../ml/README.md) — scoring worker
- [`.cursor/skills/mfa-crawler/SKILL.md`](../.cursor/skills/mfa-crawler/SKILL.md) — crawler workflow skill
