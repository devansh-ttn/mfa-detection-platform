# mfa-crawler

Playwright-based headless crawler that visits ad-inventory URLs and extracts DOM metrics into **`SignalSnapshotPayload`** documents.

## Purpose

MFA detection needs **page-level evidence** — ad density, content quality, layout signals — not just a domain name. The crawler loads each URL in Chromium, runs DOM heuristics, and produces a validated signal payload the ML pipeline can score.

The long-running **`crawler-worker`** polls Postgres for `crawl_jobs` with `status=queued`, crawls each URL, persists `signal_snapshots`, writes local evidence artifacts, and updates job status to `completed` or `failed`.

## Workflow

```
ingest API  -->  crawl_jobs (queued)  -->  worker.py / consumer.py
                                              |
                    browser.py --> dom_parser.py --> crawl.py
                                              |
                         persist.py --> signal_snapshots + evidence_hash
                         artifacts.py --> backend/evidence/{url_id}/{version}/
```

1. **`browser.py`** — Launches Chromium, navigates to the URL (`persona=direct` only for now).
2. **`dom_parser.py`** — Injects JavaScript via `page.evaluate()` to measure ad slots, above-fold ads, sticky ads, content word count, and ad-to-content ratio.
3. **`crawl.py`** — Orchestrates the crawl; captures HTML + screenshot; returns `CrawlResult`.
4. **`persist.py`** — Inserts a versioned `signal_snapshots` row with `evidence_hash` (`persona=direct`).
5. **`artifacts.py`** — Writes `screenshot.png`, `page.html`, `dom_metrics.json` per url_id/version.
6. **`consumer.py`** — Claims queued jobs from Postgres and runs `crawl_and_persist`.
7. **`smoke.py`** — CLI to test a single URL (print JSON or `--persist` to Postgres).

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

Example output:

```json
{
  "schema_version": "v1",
  "crawl_ts": "2026-07-06T08:16:22.133181Z",
  "ad_slots_count": 0,
  "content_word_count": 17,
  ...
}
```

### Docker

```bash
docker compose --profile workers build crawler-worker
docker compose --profile workers run --rm crawler-worker \
  uv run --package mfa-crawler python -m mfa_crawler.smoke
```

### Worker (queue consumer)

```bash
# Start stack + worker
docker compose up -d postgres backend-api
docker compose --profile workers up -d crawler-worker

# Ingest URLs (creates crawl_jobs with status=queued)
curl -s -X POST http://localhost:8000/api/v1/urls \
  -H 'Content-Type: application/json' \
  -d '{"urls": ["https://example.com"]}'

# Watch worker process jobs
docker compose logs -f crawler-worker

# Evidence artifacts on host
ls backend/evidence/<url_id>/1/
```

Native worker (Postgres must be running; set `DATABASE_URL`):

```bash
uv run --package mfa-crawler python -m mfa_crawler.worker
```

## Tests

```bash
# Unit tests (no browser, no Postgres)
uv run --directory crawler pytest -m "not integration" -v

# Postgres integration (persist, consumer, job poll)
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

Optional: `cp crawler/.env.example crawler/.env` for local smoke runs. Docker workers get `ENV` / `LOG_LEVEL` / `DATABASE_URL` from the **repo root** `.env` via Compose — see [`../README.md`](../README.md#environment-files-why-more-than-one).

## Module map

| File | Role |
|------|------|
| `browser.py` | Playwright lifecycle, `crawl_page()` context manager |
| `dom_parser.py` | `extract_dom_metrics(page) -> SignalFeatures` |
| `crawl.py` | `crawl_url(url) -> CrawlResult` (payload + HTML + screenshot) |
| `artifacts.py` | `write_evidence_artifacts()` to `{url_id}/{version}/` |
| `persist.py` | `crawl_and_persist(url_id)` + `persist_signal_snapshot()` |
| `consumer.py` | Postgres job poll + `process_claimed_job()` |
| `smoke.py` | CLI entrypoint (`--persist --url-id`) |
| `worker.py` | Long-running queue consumer entrypoint |
| `spike.py` / `spike_cli.py` | 100-domain crawl spike + report (POC-2.5) |

## What's next

- **POC-3.1** — Rules engine v1
- **POC-4.1** — Durable queue (Redis/SQS) replacing Postgres poll + in-memory enqueue
- **TODO(MVP):** Dual-persona crawl, 60s refresh dwell, S3 artifacts

## Crawler spike (POC-2.5)

Evaluate crawl success and DOM metrics on seed domains:

```bash
# Full 100-domain spike (requires Chromium)
uv run --package mfa-crawler python -m mfa_crawler.spike_cli

# Quick smoke (10 domains, no delay)
uv run --package mfa-crawler python -m mfa_crawler.spike_cli --domains 10 --delay-sec 0
```

Writes `crawler/artifacts/crawl_spike/report.json` and `report.md` with success rate, median/p95 crawl time, and DOM metric distributions. Baseline 100-domain report is committed under `crawler/artifacts/crawl_spike/`.

## Related docs

- [`../docs/SIGNALS.md`](../docs/SIGNALS.md) — feature schema
- [`../backend/README.md`](../backend/README.md) — ingestion API + signal reads
- [`.cursor/skills/mfa-crawler/SKILL.md`](../.cursor/skills/mfa-crawler/SKILL.md) — crawler workflow skill
