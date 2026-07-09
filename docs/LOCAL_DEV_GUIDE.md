# Local Developer Guide — MFA Detection Platform

This guide covers: what the platform does, how its pieces fit together, and how to run and manually test every layer end-to-end on your local machine.

---

## 1. What is this platform?

The **MFA (Made-For-Advertising) Detection Platform** identifies websites that exist primarily to capture programmatic ad spend rather than serve real readers. These "MFA sites" manipulate ad layout, refresh ads aggressively, and produce thin content.

The platform:

1. **Ingests** ad-inventory URLs via a REST API
2. **Crawls** each URL headlessly (Playwright + Chromium) and extracts DOM signals
3. **Scores** each URL with a rules engine + XGBoost ensemble + confidence calibrator
4. **Explains** the decision with a template (today) or LLM (MVP)
5. **Routes** uncertain cases to human reviewers (HITL)
6. **Answers** analyst questions via a RAG bot grounded in the evidence (MVP)

---

## 2. System architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│  Client / DSP                                                            │
│  POST /api/v1/urls  ──────────────────────────────────────────────────► │
└──────────────────────────────────────────────────────────────────────────┘
                                │
                ┌───────────────▼───────────────┐
                │     backend-api  :8000         │
                │  FastAPI · Alembic · Postgres  │
                │  • Normalise + dedup URLs      │
                │  • Create crawl_jobs (queued)  │
                │  • GET /jobs/{id}              │
                │  • GET /signals/{url_id}       │
                │  • GET /classifications/{id}   │
                └───────────┬───────────────────┘
                            │ Postgres (crawl_jobs)
            ┌───────────────▼───────────────┐
            │      crawler-worker            │
            │  • Crawl → signal_snapshots    │
            │  • Enqueue score_jobs          │
            └───────────────┬───────────────┘
                            │ Postgres (score_jobs)
            ┌───────────────▼───────────────┐
            │        ml-worker               │
            │  • classify_snapshot()         │
            │  • classifications + audit   │
            └───────────────────────────────┘
```

**Storage:**

| Store | Role |
|-------|------|
| Postgres 16 | URLs, crawl/score jobs, signal snapshots, classifications, audit events |
| `backend/evidence/` | Local crawl artifacts: screenshot, HTML, `dom_metrics.json` (S3 in MVP) |
| `ml/artifacts/` | Trained model binaries (`model.pkl`, `calibrator.pkl`, `metadata.json`) |

---

## 3. Repository layout

```
mfa-detection-platform/
├── docker-compose.yml          ← all local services
├── pyproject.toml              ← uv workspace root (4 Python packages)
├── uv.lock                     ← single lockfile
├── .env.example                ← copy to .env for Docker
│
├── backend/                    ← FastAPI API  (mfa-backend)
│   ├── src/mfa/
│   │   ├── api/v1/             ← urls, jobs, signals, classifications
│   │   ├── ingestion/          ← normalizer, job_poll, score_poll
│   │   ├── audit/              ← append-only audit writer
│   │   ├── scoring/            ← explanation templates (Jinja2)
│   │   ├── schemas/            ← Pydantic models (signals, classifications)
│   │   └── db/                 ← SQLAlchemy models, session
│   ├── alembic/                ← DB migrations
│   └── tests/
│
├── crawler/                    ← Playwright worker  (mfa-crawler)
│   ├── src/mfa_crawler/
│   │   ├── browser.py          ← Playwright context manager
│   │   ├── dom_parser.py       ← JS DOM metric extraction
│   │   ├── crawl.py            ← orchestrate → SignalSnapshotPayload
│   │   ├── persist.py          ← write signal_snapshots + evidence
│   │   ├── artifacts.py        ← screenshot / HTML / JSON to disk
│   │   ├── consumer.py         ← Postgres job consumer loop
│   │   ├── worker.py           ← Docker entry point
│   │   ├── smoke.py            ← one-shot smoke CLI
│   │   ├── spike.py            ← 100-domain batch evaluation
│   │   └── spike_cli.py        ← spike CLI
│   └── tests/
│
├── ml/                         ← Scoring pipeline  (mfa-ml)
│   ├── src/mfa_ml/
│   │   ├── rules/engine.py     ← 4 deterministic rules
│   │   ├── ensemble/classifier.py ← XGBoost wrapper
│   │   ├── calibration/calibrator.py ← isotonic calibration
│   │   ├── scoring/            ← tier_mapper + ClassificationOutput
│   │   ├── explainability/shap_explainer.py ← TreeSHAP top-5
│   │   ├── data/loader.py      ← FeatureExtractor + domain split
│   │   ├── consumer.py         ← score job consumer
│   │   └── worker.py           ← Docker entry point
│   ├── scripts/
│   │   ├── train.py            ← training CLI
│   │   └── evaluate.py         ← evaluation CLI
│   ├── tests/
│   └── artifacts/              ← versioned model outputs (gitignored except .gitkeep)
│
├── common/                     ← Shared logging  (mfa-common)
│   └── src/mfa_common/logging.py
│
├── data/seed/                  ← 615 gold-labelled URLs
│   ├── gold_labels.jsonl       ← machine-readable (URL → MFA_High / Non_MFA)
│   ├── gold_labels.csv         ← human-readable
│   ├── domains_summary.csv     ← 161 domains with primary labels
│   └── subset_100_domains.json ← domains used in crawl spike
│
└── docs/                       ← Architecture, signals, ADRs, roadmap
```

---

## 4. Prerequisites

| Tool | Min version | Install |
|------|-------------|---------|
| Docker | 24+ | https://docs.docker.com/get-docker/ |
| Docker Compose | v2 (`docker compose`) | bundled with Docker Desktop |
| `uv` | 0.5+ | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Python | 3.12+ | managed by uv automatically |

**macOS only — XGBoost dependency:**

```bash
brew install libomp
```

---

## 5. One-time setup

```bash
# 1. Clone
git clone https://github.com/devansh-ttn/mfa-detection-platform.git
cd mfa-detection-platform

# 2. Copy environment files
cp .env.example .env                      # used by docker compose
cp backend/.env.example backend/.env      # used by native uvicorn on host

# 3. Install Python workspace (for native dev + tests)
uv sync --all-packages

# 4. Install Playwright browser (for crawl smoke tests)
uv run --package mfa-crawler playwright install chromium
```

---

## 6. Run the full stack with Docker

All commands from the **repository root**.

### Start core services (Postgres + API)

```bash
docker compose build
docker compose up -d
```

Wait about 10 seconds, then verify:

```bash
docker compose ps
# Expected: mfa-postgres (healthy), mfa-backend-api (running)
```

### Start worker containers (optional)

```bash
docker compose --profile workers up -d
```

This adds `crawler-worker` (crawl + enqueue score jobs) and `ml-worker` (score consumer → classifications).

### Stop everything

```bash
docker compose down           # keep database volume
docker compose down -v        # wipe database (fresh start)
```

---

## 7. Manual testing — layer by layer

Work through these steps in order. Each step builds on the one above.

---

### 7.1 Health check

```bash
curl -s http://localhost:8000/health | jq
# → { "status": "ok" }

curl -s http://localhost:8000/health/db | jq
# → { "status": "ok", "database": "connected" }
```

Open **http://localhost:8000/docs** for interactive Swagger UI.

---

### 7.2 Ingest URLs

Submit URLs for crawling:

```bash
curl -s -X POST http://localhost:8000/api/v1/urls \
  -H "Content-Type: application/json" \
  -d '{
    "urls": [
      "https://example.com/article",
      "https://wealthydriver.com/markets/"
    ],
    "source_batch_id": "manual-test-01",
    "priority": 1
  }' | jq
```

**Expected response (202 Accepted):**

```json
{
  "jobs": [
    { "job_id": "...", "url": "https://example.com/article", "status": "queued" },
    { "job_id": "...", "url": "https://wealthydriver.com/markets/", "status": "queued" }
  ]
}
```

Copy a `job_id` for the next step.

---

### 7.3 Poll job status

```bash
curl -s http://localhost:8000/api/v1/jobs/<JOB_ID> | jq
# → { "job_id": "...", "status": "queued", ... }
```

Status transitions: `queued` → `running` → `completed` / `failed`

Jobs stay in `queued` until the `crawler-worker` polls them.

---

### 7.4 Batch ingest gold labels

Load the full 615-URL gold label dataset:

```bash
# Ingest all gold labels via the API
uv run --directory backend python -c "
import asyncio, httpx, json, pathlib

labels = [json.loads(l) for l in pathlib.Path('data/seed/gold_labels.jsonl').read_text().splitlines()]
urls = [r['url'] for r in labels[:20]]  # first 20 as a smoke test

async def ingest():
    async with httpx.AsyncClient() as c:
        r = await c.post('http://localhost:8000/api/v1/urls',
            json={'urls': urls, 'source_batch_id': 'gold-smoke', 'priority': 1},
            timeout=30)
        print(r.status_code, r.json())

asyncio.run(ingest())
"
```

Or use the batch script:

```bash
uv run --directory backend python scripts/seed/ingest_gold_labels.py \
  --api-url http://localhost:8000 \
  --gold-labels data/seed/gold_labels.jsonl \
  --batch-size 50
```

---

### 7.5 Smoke crawl — single URL (native)

Test the Playwright crawler directly, without any queue:

```bash
# Crawl example.com and print the signal payload
uv run --package mfa-crawler python -m mfa_crawler.smoke

# Or a specific URL
uv run --package mfa-crawler python -m mfa_crawler.smoke https://example.com/article
```

**Expected output:**

```json
{
  "schema_version": "v1",
  "crawl_ts": "2026-07-06T12:34:56Z",
  "ad_slots_count": 0,
  "ads_above_fold": 0,
  "sticky_ad_count": 0,
  "content_word_count": 17,
  "ad_to_content_ratio": 0.0,
  "refresh_events_60s": null,
  ...
}
```

All `null` fields are features not yet extracted (see `docs/SIGNALS.md`).

### 7.5a Smoke crawl — Docker

```bash
docker compose --profile workers build crawler-worker
docker compose --profile workers run --rm crawler-worker \
  uv run --package mfa-crawler python -m mfa_crawler.smoke
```

---

### 7.6 Full crawl + DB persist (native, requires Postgres running)

With Postgres running (either Docker or native), the crawler can write `signal_snapshots` directly:

```bash
# Crawl one URL and write to DB + save evidence artifacts
DATABASE_URL="postgresql+asyncpg://mfa:mfa@localhost:5432/mfa" \
uv run --package mfa-crawler python -c "
import asyncio
from mfa_crawler.persist import crawl_and_persist
import uuid

async def main():
    url_id = uuid.uuid4()  # normally comes from DB
    result = await crawl_and_persist(
        url='https://example.com',
        url_id=url_id,
    )
    print('Snapshot version:', result.version)
    print('Evidence hash:', result.evidence_hash)
    print('Evidence dir:', result.evidence_dir)

asyncio.run(main())
"
```

Evidence artifacts are written to `backend/evidence/<url_id>/<version>/`:
- `screenshot.png`
- `page.html`
- `dom_metrics.json`

---

### 7.7 End-to-end: ingest → auto-crawl via worker

With Postgres, backend API, and crawler-worker all running:

```bash
# 1. Start everything
docker compose up -d
docker compose --profile workers up -d crawler-worker

# 2. Submit a URL
curl -s -X POST http://localhost:8000/api/v1/urls \
  -H "Content-Type: application/json" \
  -d '{
    "urls": ["https://example.com/article"],
    "source_batch_id": "e2e-test",
    "priority": 1
  }' | jq '.jobs[0].job_id'

# 3. Watch the crawler pick it up
docker compose logs -f crawler-worker
# Look for: event="crawl_complete" url="https://example.com/article"

# 4. Poll the job (should transition to "completed" within ~30s)
curl -s http://localhost:8000/api/v1/jobs/<JOB_ID> | jq '.status'

# 5. Read the signal snapshot
curl -s http://localhost:8000/api/v1/signals/<URL_ID> | jq
```

---

### 7.8 Read signal snapshots

```bash
# Get all snapshots for a URL (versioned)
curl -s "http://localhost:8000/api/v1/signals/<URL_ID>?limit=10&offset=0" | jq
```

The `signals` field contains the flat JSONB document with `schema_version: "v1"` and all 16 crawl feature fields.

---

### 7.9 100-domain crawl spike

Run the evaluation spike against 100 domains from the gold label seed set:

```bash
# Run spike (uses data/seed/domains_summary.csv and gold_labels.jsonl)
uv run --package mfa-crawler python -m mfa_crawler.spike_cli \
  --domains 100 \
  --delay-sec 0.5 \
  --output-dir crawler/artifacts/crawl_spike

# View the report
cat crawler/artifacts/crawl_spike/report.md
```

The last run (committed at `crawler/artifacts/crawl_spike/report.md`) showed:
- **84% success rate** (84/100 domains)
- Median crawl time: 2.9s, P95: 9.4s
- Failures: mostly HTTP 403 (bot-blocking), DNS, timeouts

---

### 7.10 ML scoring — rules engine (offline, no DB required)

Test the rules engine independently against a sample feature dict:

```bash
uv run --package mfa-ml python -c "
from mfa_ml.rules.engine import RulesEngine

engine = RulesEngine()

# Should fire R1 (high ad density)
high_mfa = {
    'ad_to_content_ratio': 0.55,
    'ad_slots_count': 10,
    'ads_above_fold': 2,
    'content_word_count': 150,
}
match = engine.evaluate(high_mfa)
print(f'Rule {match.rule_id}: tier={match.tier}, score={match.mfa_score}')
print('Signals:', [(s.feature, s.value) for s in match.top_signals])

# Should fire R4 (clean publisher)
clean = {
    'ad_to_content_ratio': 0.02,
    'content_word_count': 800,
}
match = engine.evaluate(clean)
print(f'Rule {match.rule_id}: tier={match.tier}, score={match.mfa_score}')

# Should pass through to XGBoost
ambiguous = {'ad_to_content_ratio': 0.15, 'ad_slots_count': 3}
print('Rule match (should be None):', engine.evaluate(ambiguous))
"
```

---

### 7.11 ML scoring — XGBoost end-to-end (with synthetic data, no DB)

Train and evaluate the model on synthetic data to verify the pipeline:

```bash
uv run --package mfa-ml python -c "
import numpy as np
from mfa_ml.ensemble.classifier import MFAXGBClassifier
from mfa_ml.calibration.calibrator import IsotonicCalibrator
from mfa_ml.scoring.tier_mapper import map_tier, calibrated_confidence_from_proba
from mfa_ml.explainability.shap_explainer import SHAPExplainer
from mfa_ml.scoring.output import ClassificationOutput
from mfa.scoring.explanations.templates import render_explanation

FEATURES = [
    'ad_to_content_ratio', 'ads_above_fold', 'ad_slots_count',
    'sticky_ad_count', 'content_word_count',
]

# --- synthetic training data ---
rng = np.random.default_rng(42)
train_f = (
    [{'ad_to_content_ratio': float(rng.uniform(0.3, 0.9)),
      'ad_slots_count': int(rng.integers(5, 15)),
      'ads_above_fold': int(rng.integers(2, 8)),
      'sticky_ad_count': 0,
      'content_word_count': int(rng.integers(50, 300))} for _ in range(80)]
    +
    [{'ad_to_content_ratio': float(rng.uniform(0, 0.08)),
      'ad_slots_count': int(rng.integers(0, 3)),
      'ads_above_fold': 0,
      'sticky_ad_count': 0,
      'content_word_count': int(rng.integers(400, 1500))} for _ in range(160)]
)
train_l = [1]*80 + [0]*160

val_f = train_f[:40]
val_l = train_l[:40]

# --- train ---
clf = MFAXGBClassifier(FEATURES)
clf.train(train_f, train_l, val_f, val_l)

# --- calibrate ---
raw_probas = clf.predict_proba(val_f)
cal = IsotonicCalibrator()
cal.fit(raw_probas, np.array(val_l, dtype=np.int32))

# --- score one URL ---
test_url = {'ad_to_content_ratio': 0.6, 'ad_slots_count': 9,
            'ads_above_fold': 4, 'sticky_ad_count': 1, 'content_word_count': 120}
raw = float(clf.predict_proba([test_url])[0])
calibrated = float(cal.transform(np.array([raw]))[0])
confidence_score = calibrated_confidence_from_proba(calibrated)
tier, confidence = map_tier(calibrated, confidence_score)

# --- SHAP ---
explainer = SHAPExplainer(clf._model, FEATURES)
top_signals = explainer.explain(test_url)

# --- template explanation ---
explanation = render_explanation(tier, top_signals)

print(f'  Score   : {calibrated:.3f}')
print(f'  Tier    : {tier}')
print(f'  Confidence: {confidence}')
print(f'  Top signals:')
for s in top_signals:
    print(f'    {s.rank}. {s.feature}={s.value}  SHAP={s.contribution:+.3f}')
print(f'  Explanation:\\n{explanation}')
"
```

---

### 7.12 ML scoring — train on real data (requires crawled gold labels in DB)

After running the crawler against the gold label set, train the model on real data:

```bash
# Ensure Postgres is running and has signal_snapshots for gold label URLs
docker compose up -d postgres

# Train (loads signal_snapshots from DB + gold labels from JSONL)
uv run --package mfa-ml python ml/scripts/train.py \
  --db-url "postgresql://mfa:mfa@localhost:5432/mfa" \
  --gold-labels data/seed/gold_labels.jsonl \
  --artifact-dir ml/artifacts/v1

# Evaluate on holdout set
uv run --package mfa-ml python ml/scripts/evaluate.py \
  --db-url "postgresql://mfa:mfa@localhost:5432/mfa" \
  --gold-labels data/seed/gold_labels.jsonl \
  --artifact-dir ml/artifacts/v1
```

**POC targets:** Precision ≥ 85%, Recall ≥ 70%

The evaluation script exits with a PASS/FAIL and writes `ml/artifacts/v1/metrics.json`.

---

### 7.13 Template explanations

Test each tier's explanation template:

```bash
uv run --directory backend python -c "
from mfa.scoring.explanations.templates import render_explanation
from mfa_ml.scoring.output import SignalContribution

sigs = [
    SignalContribution(feature='ad_to_content_ratio', value=0.55, contribution=0.45, rank=1),
    SignalContribution(feature='ad_slots_count', value=9, contribution=0.30, rank=2),
]

for tier in ['MFA_High', 'MFA_Medium', 'MFA_Low', 'Non_MFA', 'Uncertain']:
    print(f'--- {tier} ---')
    print(render_explanation(tier, sigs))
    print()
"
```

---

### 7.14 End-to-end: ingest → crawl → score → read (≤30 min)

Full pipeline using Docker workers and the poc-4 `score_jobs` queue:

```bash
# 1. Start stack + workers
docker compose up -d
docker compose --profile workers up -d

# 2. Ingest URLs (smoke: 5 URLs)
uv run python scripts/seed/ingest_gold_labels.py --limit 5

# 3. List jobs and poll until completed
curl -s "http://localhost:8000/api/v1/jobs?limit=5" | python3 -m json.tool
curl -s http://localhost:8000/api/v1/jobs/<job_id> | python3 -m json.tool

# 4. Read signals + classification (after crawl + ml-worker finish)
curl -s http://localhost:8000/api/v1/signals/<url_id> | python3 -m json.tool
curl -s http://localhost:8000/api/v1/classifications/<url_id> | python3 -m json.tool

# 5. Train + evaluate (after batch crawl populates signal_snapshots)
uv run --package mfa-ml python ml/scripts/train.py \
  --db-url "postgresql://mfa:mfa@localhost:5432/mfa" \
  --gold-labels data/seed/gold_labels.jsonl \
  --artifact-dir ml/artifacts/v1
uv run --package mfa-ml python ml/scripts/evaluate.py \
  --db-url "postgresql://mfa:mfa@localhost:5432/mfa" \
  --gold-labels data/seed/gold_labels.jsonl \
  --artifact-dir ml/artifacts/v1
```

Watch worker logs while waiting:

```bash
docker compose logs -f crawler-worker ml-worker
```

Re-run evaluation on live crawled DOM features before claiming production-ready metrics.

---

## 8. Run automated tests

### Backend tests

```bash
# Unit tests (no Postgres required)
uv run --directory backend pytest tests/test_normalizer.py \
  tests/test_signals_schema.py \
  tests/test_explanations.py \
  tests/test_classifications_schema.py -v

# All tests including integration (requires Postgres on localhost:5432)
MFA_RUN_INTEGRATION=1 uv run --directory backend pytest -v
```

### Crawler tests

```bash
# Unit tests (no browser required)
uv run --package mfa-crawler pytest -m "not integration" -v

# Integration tests (requires Chromium + Postgres)
MFA_RUN_INTEGRATION=1 \
PLAYWRIGHT_SMOKE=1 \
DATABASE_URL="postgresql+asyncpg://mfa:mfa@localhost:5432/mfa" \
uv run --package mfa-crawler pytest -m integration -v
```

### ML tests

```bash
# All ML unit tests (no DB or live data required)
uv run --package mfa-ml pytest ml/tests/ -v
```

### All tests at once

```bash
uv run --directory backend pytest -v --ignore=tests/test_api.py --ignore=tests/test_signals_api.py
uv run --package mfa-crawler pytest -m "not integration" -v
uv run --package mfa-ml pytest ml/tests/ -v
```

---

## 9. Data: gold labels

The seed dataset lives in `data/seed/`:

| File | What it contains |
|------|-----------------|
| `gold_labels.jsonl` | 615 URLs with labels (`MFA_High` or `Non_MFA`), domain, page type, source |
| `gold_labels.csv` | Same data in spreadsheet format for Ad Ops review |
| `domains_summary.csv` | One row per domain (161 total) with primary label and URL count |
| `subset_100_domains.json` | 100 domain subset used in the crawl spike |

**Label distribution:** 166 `MFA_High` / 449 `Non_MFA` (≈ 1:2.7 imbalance — accounted for via `scale_pos_weight` in XGBoost)

Validate the gold labels:

```bash
python scripts/seed/validate_gold_labels.py
# Exit 0 = all records valid
```

---

## 10. Signal schema

The 16 crawl features are defined in `backend/src/mfa/schemas/signals.py` and documented in `docs/SIGNALS.md`:

| Feature | Crawler status | Description |
|---------|----------------|-------------|
| `ad_to_content_ratio` | **Extracted** | Ad pixel area / content area (0–1) |
| `ads_above_fold` | **Extracted** | Ad elements visible without scrolling |
| `ad_slots_count` | **Extracted** | Total ad-like elements on page |
| `sticky_ad_count` | **Extracted** | Fixed/sticky positioned ad elements |
| `content_word_count` | **Extracted** | Words in article/main/body text |
| `refresh_events_60s` | `null` (TODO MVP) | Ad refreshes during 60s dwell |
| `avg_refresh_interval_sec` | `null` (TODO MVP) | Mean interval between refreshes |
| All other 9 fields | `null` | Planned for later phases |

**Null convention:** `null` = not yet measured. `0` = measured and zero. Never use `0` as a placeholder for unmeasured.

---

## 11. Environment variables reference

### Docker Compose (root `.env`)

| Variable | Default | Purpose |
|----------|---------|---------|
| `POSTGRES_USER` | `mfa` | DB username |
| `POSTGRES_PASSWORD` | `mfa` | DB password |
| `POSTGRES_DB` | `mfa` | DB name |
| `DATABASE_URL` | `postgresql+asyncpg://mfa:mfa@postgres:5432/mfa` | Async SQLAlchemy (in containers) |
| `DATABASE_URL_SYNC` | `postgresql+psycopg://mfa:mfa@postgres:5432/mfa` | Alembic migrations |
| `LOG_LEVEL` | `INFO` | Structured log level |
| `ENV` | `local` | Environment label in logs |

### Native dev (backend `.env`)

Same variables but `DATABASE_URL` uses `localhost:5432` instead of `postgres:5432`.

### Crawler overrides (`crawler/.env` — optional)

| Variable | Default | Purpose |
|----------|---------|---------|
| `CRAWL_HEADLESS` | `true` | Headless Chromium |
| `CRAWL_TIMEOUT_MS` | `30000` | Navigation timeout |
| `CRAWL_USER_AGENT` | `MFA-Detection-Crawler/0.1` | Identifiable crawler UA |
| `CRAWL_POLL_INTERVAL_SEC` | `5` | Worker polling interval |
| `EVIDENCE_DIR` | `backend/evidence` | Local artifact path |

---

## 12. Troubleshooting

### Port 5432 already in use

Another Postgres instance is running. Either stop it or change the port mapping in `docker-compose.yml`:

```yaml
ports:
  - "5433:5432"  # host:container
```

Then update `DATABASE_URL` in `.env` to `...@localhost:5433/mfa`.

### API container keeps restarting

```bash
docker compose logs backend-api
```

Most common cause: Alembic migration failed because `DATABASE_URL_SYNC` uses `localhost` instead of `postgres`. Ensure the root `.env` is present and has `@postgres:5432`.

### XGBoost fails to import on macOS

```bash
brew install libomp
```

### Playwright / Chromium not found

```bash
uv run --package mfa-crawler playwright install chromium
# Or inside Docker:
docker compose --profile workers build --no-cache crawler-worker
```

### `uv sync` errors

```bash
# Clean and re-sync from repo root
uv sync --all-packages --reinstall
```

### Database schema out of date

```bash
# With Postgres running
uv run --directory backend alembic upgrade head
# Or restart backend-api container (runs migrations on start)
docker compose restart backend-api
```

---

## 13. Branch strategy

| Branch | Purpose |
|--------|---------|
| `develop` | Active integration branch — all POC/Baseline work lands here |
| `main` | Stable release (merge from `develop` when milestone exits) |

Clone and work on `develop`:

```bash
git checkout develop
git pull origin develop
```

---

## 14. What's implemented vs planned

| Task ID | Layer | Status | Notes |
|---------|-------|--------|-------|
| P0 (schema, API, seed) | Backend | **Done** | Postgres schema, ingestion API, gold labels |
| POC-1 (signal schema, batch ingest) | Backend | **Done** | `SignalFeatures`, `GET /signals`, ingest CLI |
| POC-2.1–2.2 (Playwright, DOM parser) | Crawler | **Done** | `browser.py`, `dom_parser.py`, 5 metrics |
| POC-2.3–2.6 (persist, worker, spike) | Crawler | **Done** | `persist.py`, `consumer.py`, 100-domain spike |
| POC-2 (error taxonomy) | Crawler | **Done** | `errors.py`, `crawl_error_type` skip logic (migration `002`) |
| POC-3.1 (rules engine) | ML | **Done** | 4 rules on available features |
| POC-3.2–3.3 (XGBoost, calibration) | ML | **Done** | Train CLI, isotonic calibrator, `artifacts/v1/` |
| POC-3.4–3.6 (tier mapper, SHAP, templates) | ML | **Done** | `classify_snapshot()` + full output contract |
| POC-3.7 (train + evaluate on real data) | ML | **Done (gap documented)** | `metrics.json` exists; **FAIL** vs 85%/70% — see `ml/artifacts/v1/eval_notes.md` |
| POC-4.1 (durable queue) | Backend | **Done (Postgres)** | Crawl + score poll via `FOR UPDATE SKIP LOCKED`; Redis/SQS is MVP |
| POC-4.2 (crawl → score enqueue) | Workers | **Done** | `score_poll.py`, crawler enqueues after `crawl_and_persist` |
| POC-4.3 (ml-worker score consumer) | Workers | **Done** | `mfa_ml/consumer.py` → `classifications` rows |
| POC-4.4 (audit writer) | Backend | **Done** | `url.ingested`, `crawl.completed`, `classification.scored` |
| POC-4.5 (classifications API) | API | **Done** | `GET /classifications/{url_id}` + `/history` |
| POC-5.2 (list jobs endpoint) | API | **Done** | `GET /api/v1/jobs` with `status` / `domain` filters |
| POC-5 (batch eval, HITL export, demo) | All | **In progress** | Full gold-label batch crawl, reviewer CSV, OpenAPI examples |
| MVP (dual-persona, LLM, RAG, review UI) | All | **Not started** | Frontend at MVP-4.1; see `docs/ROADMAP.md` |

**E2E path (live):** `POST /urls` → `crawl_jobs` → crawler-worker → `signal_snapshots` → `score_jobs` → ml-worker → `classifications` + `audit_events` → `GET /classifications/{url_id}`

---

## 15. Key design decisions

| Decision | Choice | Why |
|----------|--------|-----|
| Primary classifier | Rules + XGBoost | LLM not used for classification (ADR-001) |
| Scoring granularity | URL / page path | Domain-only is gameable |
| Evidence storage | Local `backend/evidence/` | S3 deferred to MVP |
| Queue | Postgres `FOR UPDATE SKIP LOCKED` | Redis/SQS deferred to MVP |
| SHAP library | External `shap` (0.52.0 + llvmlite 0.48.0 + numba 0.66.0) | Exact TreeSHAP values, Python 3.14 compatible |
| ML train/val split | Domain-level stratified 80/20 | Prevents domain leakage |
| Null imputation | Sentinel `-1.0` | XGBoost handles it natively via `missing` param |

---

## 16. Useful one-liners

```bash
# View all Postgres tables
docker exec -it mfa-postgres psql -U mfa -d mfa -c "\dt"

# Count signal_snapshots
docker exec -it mfa-postgres psql -U mfa -d mfa \
  -c "SELECT COUNT(*) FROM signal_snapshots;"

# Latest 5 crawl jobs with status
docker exec -it mfa-postgres psql -U mfa -d mfa \
  -c "SELECT id, status, created_at FROM crawl_jobs ORDER BY created_at DESC LIMIT 5;"

# View a signal snapshot's features
docker exec -it mfa-postgres psql -U mfa -d mfa \
  -c "SELECT signals FROM signal_snapshots ORDER BY created_at DESC LIMIT 1;" \
  | python3 -c "import sys, json; [print(json.dumps(json.loads(l.strip()), indent=2)) for l in sys.stdin if '{' in l]"

# Follow all container logs simultaneously
docker compose logs -f

# Rebuild a single service
docker compose build --no-cache backend-api
docker compose up -d backend-api
```
