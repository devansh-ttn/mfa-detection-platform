# Local Developer Guide — MFA Detection Platform

This guide covers: what the platform does, how its pieces fit together, and **step-by-step local testing** with expected commands and API responses.

**Quick start:** [§5 Setup](#5-one-time-setup) → [§6 Docker](#6-run-the-full-stack-with-docker) → [§7 Walkthrough](#7-local-testing-walkthrough-step-by-step) (start at [§7.1](#71-health-check)).

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

All commands from the **repository root** unless noted.

```bash
# 1. Clone and checkout develop
git clone https://github.com/devansh-ttn/mfa-detection-platform.git
cd mfa-detection-platform
git checkout develop

# 2. Copy environment files
cp .env.example .env                      # Docker Compose (Postgres host = postgres)
cp backend/.env.example backend/.env      # Native uvicorn (Postgres host = localhost)

# 3. Install Python workspace (native dev + tests)
uv sync --all-packages

# 4. Install Playwright Chromium (native crawl smoke tests)
uv run --package mfa-crawler playwright install chromium
```

**Optional:** install `jq` for pretty JSON in curl examples. All examples also work with `uv run python -m json.tool`.

---

## 6. Run the full stack with Docker

### Step 6.1 — Build and start core services

Starts **Postgres** and **backend-api** (migrations run on API startup).

```bash
docker compose build
docker compose up -d
```

Wait ~10 seconds, then verify:

```bash
docker compose ps
```

**Expected:**

```
NAME              STATUS
mfa-postgres      Up (healthy)
mfa-backend-api   Up
```

Quick health check:

```bash
curl -s http://localhost:8000/health | uv run python -m json.tool
```

**Expected response:**

```json
{
  "status": "ok",
  "env": "local"
}
```

(`env` may show `poc` if set in your `.env`.)

### Step 6.2 — Start worker containers

Workers are behind the `workers` profile. Start them **after** core services are healthy:

```bash
docker compose --profile workers up -d
```

This starts:

| Container | Role |
|-----------|------|
| `crawler-worker` | Polls `crawl_jobs` → Playwright crawl → `signal_snapshots` → enqueues `score_jobs` |
| `ml-worker` | Polls `score_jobs` → `classify_snapshot()` → `classifications` + audit |

**Important:** `ml-worker` requires `ml/artifacts/v1/model.pkl` and `calibrator.pkl`. If those files are missing, the container will crash-loop (see [§12 ml-worker crash](#ml-worker-keeps-restarting-file-not-found-artifactsmodelpkl)). Generate artifacts in [§7.8](#78-generate-ml-artifacts-before-ml-worker) before relying on scoring.

```bash
docker compose ps
```

**Expected (all four running):**

```
mfa-postgres        Up (healthy)
mfa-backend-api     Up
mfa-crawler-worker  Up
mfa-ml-worker       Up
```

Follow logs:

```bash
docker compose logs -f backend-api crawler-worker ml-worker
```

### Step 6.3 — Stop / reset

```bash
docker compose down           # keep database volume
docker compose down -v        # wipe database (fresh start)
```

---

## 7. Local testing walkthrough (step by step)

Work through these steps **in order** on a fresh stack. Each step explains what to run, what you should see, and what to copy for the next step.

**Pipeline overview:**

```
POST /urls → crawl_jobs → crawler-worker → signal_snapshots → score_jobs
    → ml-worker → classifications + audit_events → GET /classifications/{url_id}
```

| Step | What you verify |
|------|-----------------|
| [7.1](#71-health-check) | API + Postgres reachable |
| [7.2](#72-ingest-a-url) | URL accepted, `crawl_job` created |
| [7.3](#73-poll-crawl-job-status) | Crawler picks up job, status → `completed` |
| [7.4](#74-list-crawl-jobs) | List/filter jobs (optional) |
| [7.5](#75-read-signal-snapshots) | DOM features persisted |
| [7.6](#76-verify-score-job-queued) | Score job enqueued after crawl |
| [7.7](#77-re-ingest-if-crawl-ran-before-ml-worker) | Re-score if ml-worker was down during crawl |
| [7.8](#78-generate-ml-artifacts-before-ml-worker) | `model.pkl` + `calibrator.pkl` exist |
| [7.9](#79-start-or-restart-ml-worker) | ml-worker loads artifacts and scores |
| [7.10](#710-read-classification) | Tier, score, explanation returned |
| [7.11](#711-full-e2e-copy-paste) | All steps in one script |

**Tip:** Use `https://example.com/` for smoke tests — it returns HTTP 200. Paths like `/article` often 404 and produce `status: "failed"`.

Open **http://localhost:8000/docs** anytime for interactive Swagger UI.

---

### 7.1 Health check

**Command:**

```bash
curl -s http://localhost:8000/health | uv run python -m json.tool
curl -s http://localhost:8000/health/db | uv run python -m json.tool
```

**Expected responses:**

```json
{ "status": "ok", "env": "local" }
```

```json
{ "status": "ok", "database": "connected" }
```

If `/health/db` fails, Postgres is not reachable — check `docker compose ps` and [§12](#12-troubleshooting).

---

### 7.2 Ingest a URL

Submit one URL for crawling. The API normalises, deduplicates, and creates a `crawl_jobs` row with `status: "queued"`.

**Command:**

```bash
curl -s -X POST http://localhost:8000/api/v1/urls \
  -H "Content-Type: application/json" \
  -d '{
    "urls": ["https://example.com/"],
    "source_batch_id": "local-smoke-01",
    "priority": 1
  }' | uv run python -m json.tool
```

**Expected response (HTTP 202):**

```json
{
  "jobs": [
    {
      "job_id": "3954a939-2b7a-4880-af20-11dd75a4c9f9",
      "url_id": "a2de4dc3-8c6d-471b-8e79-3c4713aa65a6",
      "normalized_url": "https://example.com/",
      "status": "queued",
      "idempotency_key": "20adc95187ee9ad47fa823638c54221649f761cc55399b21bf68d80456ec3a41",
      "duplicate": false
    }
  ],
  "accepted": 1,
  "duplicate": 0,
  "invalid": []
}
```

**Save these for later steps:**

```bash
export JOB_ID="<job_id from response>"
export URL_ID="<url_id from response>"
```

Re-submitting the same URL + `source_batch_id` returns `"duplicate": true` and does not create a new job.

---

### 7.3 Poll crawl job status

Jobs stay `queued` until `crawler-worker` claims them. With workers running, `example.com` typically completes in **5–30 seconds**.

**Command:**

```bash
curl -s "http://localhost:8000/api/v1/jobs/${JOB_ID}" | uv run python -m json.tool
```

**Expected while waiting:**

```json
{
  "job_id": "...",
  "url_id": "...",
  "status": "queued",
  "url": "https://example.com/",
  "normalized_url": "https://example.com/",
  "domain": "example.com",
  "priority": 1,
  "source_batch_id": "local-smoke-01",
  "error_message": null,
  "created_at": "...",
  "updated_at": "..."
}
```

**Expected on success:**

```json
{
  "status": "completed",
  "error_message": null,
  ...
}
```

**Expected on failure (e.g. 404 URL):**

```json
{
  "status": "failed",
  "error_message": "HTTP 404 — page not found: 'https://example.com/article'",
  ...
}
```

**Status transitions:** `queued` → `running` → `completed` | `failed`

**Watch crawler logs:**

```bash
docker compose logs -f crawler-worker
```

Look for structured events such as `signal_snapshot_persisted` and `crawl_job` completion. If status stays `queued`, ensure workers are up:

```bash
docker compose --profile workers up -d crawler-worker
```

---

### 7.4 List crawl jobs

List recent jobs with optional filters.

**Command:**

```bash
curl -s "http://localhost:8000/api/v1/jobs?limit=5" | uv run python -m json.tool
curl -s "http://localhost:8000/api/v1/jobs?status=completed&domain=example.com" | uv run python -m json.tool
```

**Expected:** JSON **array** of job objects (same shape as §7.3), newest first.

---

### 7.5 Read signal snapshots

After `status: "completed"`, the crawler wrote a versioned row to `signal_snapshots`.

**Command:**

```bash
curl -s "http://localhost:8000/api/v1/signals/${URL_ID}" | uv run python -m json.tool
```

**Expected response (truncated):**

```json
{
  "url_id": "a2de4dc3-8c6d-471b-8e79-3c4713aa65a6",
  "snapshots": [
    {
      "snapshot_id": "d17a02b8-6cf5-44fb-9873-ad6a58616064",
      "url_id": "a2de4dc3-8c6d-471b-8e79-3c4713aa65a6",
      "version": 1,
      "signals": {
        "schema_version": "v1",
        "crawl_ts": "2026-07-09T20:59:38.830249Z",
        "ad_to_content_ratio": 0.0,
        "ads_above_fold": 0,
        "ad_slots_count": 0,
        "sticky_ad_count": 0,
        "content_word_count": 17,
        "refresh_events_60s": null
      },
      "evidence_hash": "c4eea93257367753dd5804aef0dd554fdaa5fefc8dec70fb5110e6b35fa666cb",
      "persona": "direct",
      "crawl_duration_sec": 0.536,
      "created_at": "2026-07-09T20:59:38.857899Z"
    }
  ],
  "total": 1,
  "limit": 20,
  "offset": 0
}
```

Evidence files (screenshot, HTML, `dom_metrics.json`) are under `backend/evidence/<url_id>/<version>/`.

---

### 7.6 Verify score job queued

After a successful crawl, the crawler enqueues a `score_jobs` row for `ml-worker`.

**Command:**

```bash
docker exec mfa-postgres psql -U mfa -d mfa -c \
  "SELECT id, status, signal_snapshot_id FROM score_jobs ORDER BY created_at DESC LIMIT 3;"
```

**Expected:** One row with `status = queued` (or `completed` if ml-worker already scored it).

---

### 7.7 Re-ingest if crawl ran before ml-worker

If you crawled **before** ml-worker had valid artifacts, the score job may have failed. After generating artifacts (§7.8), re-submit the URL with a **new** `source_batch_id` to trigger a fresh crawl + score:

```bash
curl -s -X POST http://localhost:8000/api/v1/urls \
  -H "Content-Type: application/json" \
  -d '{"urls":["https://example.com/"],"source_batch_id":"local-smoke-02","priority":1}' \
  | uv run python -m json.tool
```

Update `JOB_ID` and `URL_ID` from the response, then repeat §7.3–§7.10.

---

### 7.8 Generate ML artifacts (before ml-worker)

`ml-worker` loads binaries from `ml/artifacts/v1/` (mounted as `/artifacts` in Docker). Required files:

| File | Purpose |
|------|---------|
| `model.pkl` | Trained XGBoost classifier |
| `calibrator.pkl` | Isotonic calibrator |
| `metadata.json` | Feature schema version gate |

#### Option A — Production path (real crawled data)

Ingest and crawl gold-label URLs first, then train:

```bash
# Ingest 50 URLs (API must be running; workers recommended)
uv run python scripts/seed/ingest_gold_labels.py --limit 50

# Wait for crawls to finish (poll jobs or watch logs), then train
uv run --package mfa-ml python ml/scripts/train.py \
  --db-url "postgresql://mfa:mfa@localhost:5432/mfa" \
  --gold-labels data/seed/gold_labels.jsonl \
  --artifact-dir ml/artifacts/v1
```

Training needs **matching** `signal_snapshots` for gold-label URLs. If you see `no_training_samples`, crawls have not finished yet.

#### Option B — Dev bootstrap (synthetic model, smoke test only)

For a quick local score without waiting for batch crawls:

```bash
uv run --package mfa-ml python -c "
import pickle, numpy as np
from pathlib import Path
from mfa_ml.ensemble.classifier import MFAXGBClassifier
from mfa_ml.calibration.calibrator import IsotonicCalibrator

FEATURES = ['ad_to_content_ratio','ads_above_fold','ad_slots_count','sticky_ad_count','content_word_count']
rng = np.random.default_rng(42)
train_f = (
    [{'ad_to_content_ratio': float(rng.uniform(0.3,0.9)), 'ad_slots_count': int(rng.integers(5,15)),
      'ads_above_fold': int(rng.integers(2,8)), 'sticky_ad_count': 0,
      'content_word_count': int(rng.integers(50,300))} for _ in range(80)]
    + [{'ad_to_content_ratio': float(rng.uniform(0,0.08)), 'ad_slots_count': int(rng.integers(0,3)),
      'ads_above_fold': 0, 'sticky_ad_count': 0,
      'content_word_count': int(rng.integers(400,1500))} for _ in range(160)]
)
train_l = [1]*80 + [0]*160
val_f, val_l = train_f[:40], train_l[:40]

clf = MFAXGBClassifier(FEATURES)
clf.train(train_f, train_l, val_f, val_l)
cal = IsotonicCalibrator()
cal.fit(clf.predict_proba(val_f), np.array(val_l, dtype=np.int32))

out = Path('ml/artifacts/v1')
out.mkdir(parents=True, exist_ok=True)
clf.save(out)
with open(out / 'calibrator.pkl', 'wb') as f:
    pickle.dump(cal, f)
print('Wrote', out / 'model.pkl', 'and calibrator.pkl (dev bootstrap — not for production eval)')
"
```

> **Note:** The dev bootstrap model is trained on random synthetic data. It verifies the scoring *pipeline* but tiers on real pages (e.g. `example.com`) may be wrong. Use Option A before evaluating precision/recall.

**Verify:**

```bash
ls ml/artifacts/v1/model.pkl ml/artifacts/v1/calibrator.pkl
```

---

### 7.9 Start or restart ml-worker

After artifacts exist:

```bash
docker compose --profile workers up -d ml-worker
docker compose logs -f ml-worker
```

**Expected log lines:**

```
ml_worker_ready ... artifact_dir=/artifacts
ml_consumer_started ... poll_interval_sec=5
```

Then `classification.scored` audit events appear as jobs are processed.

---

### 7.10 Read classification

Once ml-worker completes a score job:

**Command:**

```bash
curl -s "http://localhost:8000/api/v1/classifications/${URL_ID}" | uv run python -m json.tool
```

**Expected response (shape; values depend on signals + model):**

```json
{
  "classification_id": "8f3c2a1b-....",
  "url_id": "a2de4dc3-8c6d-471b-8e79-3c4713aa65a6",
  "signal_snapshot_id": "d17a02b8-6cf5-44fb-9873-ad6a58616064",
  "tier": "Non_MFA",
  "mfa_score": 0.1234,
  "confidence": "medium",
  "top_signals": [
    {
      "feature": "content_word_count",
      "value": 17,
      "contribution": 0.12,
      "rank": 1
    }
  ],
  "explanation": "This page shows low MFA risk...",
  "evidence_hash": "c4eea93257367753dd5804aef0dd554fdaa5fefc8dec70fb5110e6b35fa666cb",
  "classifier": "xgboost",
  "schema_version": "v1",
  "created_at": "2026-07-09T21:05:00.000000Z"
}
```

**History endpoint:**

```bash
curl -s "http://localhost:8000/api/v1/classifications/${URL_ID}/history?limit=5" | uv run python -m json.tool
```

**If you get 404 `classification_not_found`:** ml-worker has not scored yet — check §7.8–§7.9 and score job status:

```bash
docker exec mfa-postgres psql -U mfa -d mfa -c \
  "SELECT status, error_message FROM score_jobs ORDER BY created_at DESC LIMIT 3;"
```

---

### 7.11 Full E2E copy-paste

Run from repo root with Docker installed. Assumes fresh stack.

```bash
# 1. Start everything
docker compose up -d
docker compose --profile workers up -d

# 2. Health
curl -s http://localhost:8000/health/db | uv run python -m json.tool

# 3. Dev-bootstrap ML artifacts (skip if model.pkl already exists)
test -f ml/artifacts/v1/model.pkl || uv run --package mfa-ml python -c "
import pickle, numpy as np
from pathlib import Path
from mfa_ml.ensemble.classifier import MFAXGBClassifier
from mfa_ml.calibration.calibrator import IsotonicCalibrator
F=['ad_to_content_ratio','ads_above_fold','ad_slots_count','sticky_ad_count','content_word_count']
rng=np.random.default_rng(42)
tf=[{'ad_to_content_ratio':float(rng.uniform(0.3,0.9)),'ad_slots_count':int(rng.integers(5,15)),'ads_above_fold':int(rng.integers(2,8)),'sticky_ad_count':0,'content_word_count':int(rng.integers(50,300))} for _ in range(80)]+[{'ad_to_content_ratio':float(rng.uniform(0,0.08)),'ad_slots_count':int(rng.integers(0,3)),'ads_above_fold':0,'sticky_ad_count':0,'content_word_count':int(rng.integers(400,1500))} for _ in range(160)]
tl=[1]*80+[0]*160
vf,vl=tf[:40],tl[:40]
c=MFAXGBClassifier(F); c.train(tf,tl,vf,vl)
cal=IsotonicCalibrator(); cal.fit(c.predict_proba(vf), np.array(vl,dtype=np.int32))
o=Path('ml/artifacts/v1'); o.mkdir(parents=True, exist_ok=True); c.save(o)
pickle.dump(cal, open(o/'calibrator.pkl','wb'))
"

# 4. Restart ml-worker so it picks up artifacts
docker compose --profile workers up -d ml-worker

# 5. Ingest + capture IDs
RESP=$(curl -s -X POST http://localhost:8000/api/v1/urls \
  -H "Content-Type: application/json" \
  -d '{"urls":["https://example.com/"],"source_batch_id":"e2e-script","priority":1}')
echo "$RESP" | uv run python -m json.tool
export JOB_ID=$(echo "$RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['jobs'][0]['job_id'])")
export URL_ID=$(echo "$RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['jobs'][0]['url_id'])")

# 6. Poll until completed (max ~60s)
for i in $(seq 1 12); do
  STATUS=$(curl -s "http://localhost:8000/api/v1/jobs/${JOB_ID}" | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])")
  echo "Attempt $i: status=$STATUS"
  test "$STATUS" = "completed" && break
  sleep 5
done

# 7. Signals + classification
curl -s "http://localhost:8000/api/v1/signals/${URL_ID}" | uv run python -m json.tool
curl -s "http://localhost:8000/api/v1/classifications/${URL_ID}" | uv run python -m json.tool
```

---

## 7A. Advanced layer tests

These sections test individual components without the full pipeline.

### 7A.1 Batch ingest gold labels

```bash
# Smoke: 5 URLs
uv run python scripts/seed/ingest_gold_labels.py --limit 5

# Full dataset (615 URLs, batched at 500/request)
uv run python scripts/seed/ingest_gold_labels.py

# Dry run (no API calls)
uv run python scripts/seed/ingest_gold_labels.py --limit 5 --dry-run
```

**Expected terminal output:**

```
Ingesting 5 URL(s) with source_batch_id='seed-v1-2026-07-03'
  batch 1: sent=5 accepted=5 duplicate=0 invalid=0
    job_id=... url_id=... (accepted)
Done: 1 batch(es), accepted=5, duplicate=0, invalid=0
```

Requires API running (`docker compose up -d`).

---

### 7A.2 Smoke crawl — single URL (native, no DB)

Test Playwright extraction without the job queue:

```bash
uv run --package mfa-crawler python -m mfa_crawler.smoke https://example.com/
```

**Expected:** JSON feature block printed to stdout (log lines may precede it):

```json
{
  "schema_version": "v1",
  "crawl_ts": "2026-07-09T21:00:12.913611Z",
  "ad_to_content_ratio": 0.0,
  "ads_above_fold": 0,
  "ad_slots_count": 0,
  "sticky_ad_count": 0,
  "content_word_count": 17,
  "refresh_events_60s": null
}
```

Null fields are features not yet extracted — see `docs/SIGNALS.md`.

---

### 7A.3 Smoke crawl — Docker

```bash
docker compose --profile workers build crawler-worker
docker compose --profile workers run --rm crawler-worker \
  python -m mfa_crawler.smoke https://example.com/
```

---

### 7A.4 Crawl + DB persist (native)

Requires Postgres on `localhost:5432` and a `urls` row already in the DB (create one via §7.2 and use its `url_id`):

```bash
export URL_ID="<url_id from ingest>"

DATABASE_URL="postgresql+asyncpg://mfa:mfa@localhost:5432/mfa" \
uv run --package mfa-crawler python -c "
import asyncio, uuid
from mfa_crawler.persist import crawl_and_persist

async def main():
    result = await crawl_and_persist(uuid.UUID('${URL_ID}'))
    print('Snapshot version:', result.version)
    print('Evidence hash:', result.evidence_hash)
    print('Artifact dir:', result.artifact_dir)

asyncio.run(main())
"
```

---

### 7A.5 100-domain crawl spike

Offline evaluation against seed domains (no API required):

```bash
uv run --package mfa-crawler python -m mfa_crawler.spike_cli \
  --domains 100 \
  --delay-sec 0.5 \
  --output-dir crawler/artifacts/crawl_spike

cat crawler/artifacts/crawl_spike/report.md
```

Last committed spike: **84% success** (84/100 domains); failures mostly HTTP 403, DNS, timeouts.

---

### 7A.6 ML scoring — rules engine (offline)

```bash
uv run --package mfa-ml python -c "
from mfa_ml.rules.engine import RulesEngine

engine = RulesEngine()

high_mfa = {'ad_to_content_ratio': 0.55, 'ad_slots_count': 10, 'ads_above_fold': 2, 'content_word_count': 150}
match = engine.evaluate(high_mfa)
print(f'Rule {match.rule_id}: tier={match.tier}, score={match.mfa_score}')

clean = {'ad_to_content_ratio': 0.02, 'content_word_count': 800}
match = engine.evaluate(clean)
print(f'Rule {match.rule_id}: tier={match.tier}, score={match.mfa_score}')

ambiguous = {'ad_to_content_ratio': 0.15, 'ad_slots_count': 3}
print('Rule match (expect None):', engine.evaluate(ambiguous))
"
```

**Expected:**

```
Rule R1: tier=MFA_High, score=...
Rule R4: tier=Non_MFA, score=...
Rule match (expect None): None
```

---

### 7A.7 ML scoring — XGBoost pipeline (offline, synthetic)

```bash
uv run --package mfa-ml python -c "
import numpy as np
from mfa_ml.ensemble.classifier import MFAXGBClassifier
from mfa_ml.calibration.calibrator import IsotonicCalibrator
from mfa_ml.scoring.tier_mapper import map_tier, calibrated_confidence_from_proba
from mfa_ml.explainability.shap_explainer import SHAPExplainer
from mfa.scoring.explanations.templates import render_explanation

FEATURES = ['ad_to_content_ratio','ads_above_fold','ad_slots_count','sticky_ad_count','content_word_count']
rng = np.random.default_rng(42)
train_f = ([{'ad_to_content_ratio': float(rng.uniform(0.3,0.9)), 'ad_slots_count': int(rng.integers(5,15)),
  'ads_above_fold': int(rng.integers(2,8)), 'sticky_ad_count': 0,
  'content_word_count': int(rng.integers(50,300))} for _ in range(80)]
  + [{'ad_to_content_ratio': float(rng.uniform(0,0.08)), 'ad_slots_count': int(rng.integers(0,3)),
  'ads_above_fold': 0, 'sticky_ad_count': 0,
  'content_word_count': int(rng.integers(400,1500))} for _ in range(160)])
train_l = [1]*80 + [0]*160
val_f, val_l = train_f[:40], train_l[:40]

clf = MFAXGBClassifier(FEATURES)
clf.train(train_f, train_l, val_f, val_l)
cal = IsotonicCalibrator()
cal.fit(clf.predict_proba(val_f), np.array(val_l, dtype=np.int32))

test_url = {'ad_to_content_ratio': 0.6, 'ad_slots_count': 9, 'ads_above_fold': 4,
            'sticky_ad_count': 1, 'content_word_count': 120}
raw = float(clf.predict_proba([test_url])[0])
calibrated = float(cal.transform(np.array([raw]))[0])
conf_score = calibrated_confidence_from_proba(calibrated)
tier, confidence = map_tier(calibrated, conf_score)

explainer = SHAPExplainer(clf.model, FEATURES)
top_signals = explainer.explain(test_url)
explanation = render_explanation(tier, top_signals)

print(f'Score: {calibrated:.3f}  Tier: {tier}  Confidence: {confidence}')
print(explanation)
"
```

---

### 7A.8 Train + evaluate on real crawled data

After gold-label URLs are crawled into `signal_snapshots`:

```bash
docker compose up -d postgres

uv run --package mfa-ml python ml/scripts/train.py \
  --db-url "postgresql://mfa:mfa@localhost:5432/mfa" \
  --gold-labels data/seed/gold_labels.jsonl \
  --artifact-dir ml/artifacts/v1

uv run --package mfa-ml python ml/scripts/evaluate.py \
  --db-url "postgresql://mfa:mfa@localhost:5432/mfa" \
  --gold-labels data/seed/gold_labels.jsonl \
  --artifact-dir ml/artifacts/v1
```

**POC targets:** Precision ≥ 85%, Recall ≥ 70%

Evaluate prints `PASS` or `FAIL` and writes `ml/artifacts/v1/metrics.json` with a `meets_targets` flag.

---

### 7A.9 Template explanations

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
uv run python scripts/seed/validate_gold_labels.py
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
| `CRAWL_POLL_INTERVAL_SEC` | `5` | Crawler worker polling interval |
| `EVIDENCE_DIR` | `backend/evidence` | Local artifact path (native); `/app/evidence` in Docker |

### ML worker overrides (Docker Compose sets these)

| Variable | Default (Docker) | Purpose |
|----------|------------------|---------|
| `ARTIFACT_DIR` | `/artifacts` | Directory containing `model.pkl`, `calibrator.pkl`, `metadata.json` |
| `SCORE_POLL_INTERVAL_SEC` | `5` | ml-worker polling interval when queue is empty |

Native dev: `export ARTIFACT_DIR=ml/artifacts/v1` before `python -m mfa_ml.worker`.

---

## 12. Troubleshooting

### Job stays `queued`

`crawler-worker` is not running or cannot reach Postgres.

```bash
docker compose --profile workers up -d crawler-worker
docker compose logs crawler-worker
```

### Job status `failed` with HTTP 404

The URL path does not exist. Use a live URL (e.g. `https://example.com/`) or pick a URL from `data/seed/gold_labels.jsonl`.

### ml-worker keeps restarting (`FileNotFoundError: '/artifacts/model.pkl'`)

ML binaries are missing. Generate them per [§7.8](#78-generate-ml-artifacts-before-ml-worker), then restart:

```bash
docker compose --profile workers up -d ml-worker
```

### `classification_not_found` on GET /classifications

Either ml-worker has not scored yet, or score job failed. Check:

```bash
docker compose logs ml-worker
docker exec mfa-postgres psql -U mfa -d mfa -c \
  "SELECT status, error_message FROM score_jobs ORDER BY created_at DESC LIMIT 5;"
```

Re-ingest with a new `source_batch_id` after fixing artifacts (§7.7).

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
| POC-5.6 (E2E walkthrough) | Docs | **Done** | This guide §7 + §7.11 |
| POC-5 (batch eval, HITL export) | All | **In progress** | Full gold-label batch crawl, reviewer CSV, OpenAPI examples |
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
