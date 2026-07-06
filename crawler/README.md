# mfa-crawler

Playwright-based headless crawler that visits ad-inventory URLs and extracts DOM metrics into **`SignalSnapshotPayload`** documents.

## Purpose

MFA detection needs **page-level evidence** — ad density, content quality, layout signals — not just a domain name. The crawler loads each URL in Chromium, runs DOM heuristics, and produces a validated signal payload the ML pipeline can score.

The long-running **`crawler-worker`** container will dequeue crawl jobs and persist snapshots. Today you can run crawls directly via the **smoke CLI** while queue wiring is still in progress.

## Workflow

```
URL  -->  browser.py (Playwright)  -->  dom_parser.py  -->  crawl.py
                |                              |                  |
           navigate page              extract 5 core         SignalSnapshotPayload
           (direct persona)            DOM metrics          (schema_version: v1)
```

1. **`browser.py`** — Launches Chromium, navigates to the URL (`persona=direct` only for now).
2. **`dom_parser.py`** — Injects JavaScript via `page.evaluate()` to measure ad slots, above-fold ads, sticky ads, content word count, and ad-to-content ratio.
3. **`crawl.py`** — Orchestrates the crawl and returns `(SignalSnapshotPayload, duration_sec)`.
4. **`smoke.py`** — CLI to test a single URL and print JSON output.

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

### Worker stub

The default container command runs `mfa_crawler.worker` — a heartbeat loop until queue consumption is wired (POC-2.6):

```bash
docker compose --profile workers up -d crawler-worker
docker compose logs -f crawler-worker
```

## Tests

```bash
# Unit tests (no browser)
uv run --directory crawler pytest -m "not integration" -v

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

Optional: `cp crawler/.env.example crawler/.env` for local smoke runs. Docker workers get `ENV` / `LOG_LEVEL` / `DATABASE_URL` from the **repo root** `.env` via Compose — see [`../README.md`](../README.md#environment-files-why-more-than-one).

## Module map

| File | Role |
|------|------|
| `browser.py` | Playwright lifecycle, `crawl_page()` context manager |
| `dom_parser.py` | `extract_dom_metrics(page) -> SignalFeatures` |
| `crawl.py` | `crawl_url(url) -> (SignalSnapshotPayload, float)` |
| `smoke.py` | CLI entrypoint |
| `worker.py` | Long-running worker stub (queue consumer pending) |

## What's next

- **POC-2.3** — Persist `signal_snapshots` + `evidence_hash` to Postgres
- **POC-2.4** — Save screenshot, HTML, `dom_metrics.json` under `backend/evidence/`
- **POC-2.6** — Consume crawl queue, update `crawl_jobs.status`
- **TODO(MVP):** Dual-persona crawl, 60s refresh dwell, S3 artifacts

## Related docs

- [`../docs/SIGNALS.md`](../docs/SIGNALS.md) — feature schema
- [`../backend/README.md`](../backend/README.md) — ingestion API + signal reads
- [`.cursor/skills/mfa-crawler/SKILL.md`](../.cursor/skills/mfa-crawler/SKILL.md) — crawler workflow skill
