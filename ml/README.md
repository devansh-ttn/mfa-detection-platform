# mfa-ml

Rules engine + gradient-boosted classifier for MFA risk scoring. Runs as a **worker** off the API hot path.

## Purpose

After the crawler extracts DOM signals into `signal_snapshots`, the ML worker loads those features, runs a **rules engine** and **XGBoost ensemble**, calibrates confidence, maps to an MFA tier, and writes a `classifications` row with `top_signals` and a template explanation.

**Important:** LLM is not used for classification (see ADR-001). LLM is reserved for explanations and RAG in later milestones.

## Workflow (live)

```
score_jobs (queued)  -->  ml-worker (consumer.py)
                                |
                    load signal_snapshots.signals
                                |
              classify_snapshot() — rules -> XGBoost -> calibrator -> tier
                                |
                    SHAP top-5 + Jinja2 explanation
                                |
              write classifications + audit_events (classification.scored)
```

1. **Poll** — `claim_next_score_job()` picks up a queued score job (`FOR UPDATE SKIP LOCKED`).
2. **Load** — Read `signal_snapshots.signals` + `evidence_hash` for the job's snapshot.
3. **Score** — `classify_snapshot()` runs rules short-circuit or XGBoost + isotonic calibration.
4. **Explain** — SHAP attributions → `top_signals`; Jinja2 template → `explanation`.
5. **Persist** — Insert `classifications` row; append `classification.scored` audit event; mark job `completed`.

## Current state

The **`ml-worker`** is **live** — it polls Postgres `score_jobs`, scores via `classify_snapshot()`, and persists results. Artifacts are loaded from `ARTIFACT_DIR` (default `ml/artifacts/v1`).

```bash
docker compose --profile workers up -d ml-worker
docker compose logs -f ml-worker
```

## Package layout

| Path | Role |
|------|------|
| `src/mfa_ml/worker.py` | Docker entrypoint — loads artifacts, runs consumer loop |
| `src/mfa_ml/consumer.py` | Score job poll + classify + persist |
| `src/mfa_ml/scoring/pipeline.py` | `classify_snapshot()` orchestrator |
| `src/mfa_ml/scoring/artifact_loader.py` | Load model + calibrator + SHAP from `artifacts/` |
| `src/mfa_ml/scoring/explanation.py` | Jinja2 template renderer (5 tier templates) |
| `src/mfa_ml/scoring/tier_mapper.py` | Tier bands + calibrated confidence |
| `src/mfa_ml/scoring/output.py` | `ClassificationOutput` contract |
| `src/mfa_ml/rules/engine.py` | 4 deterministic rules (R1–R4) |
| `src/mfa_ml/ensemble/classifier.py` | `MFAXGBClassifier` wrapper |
| `src/mfa_ml/calibration/calibrator.py` | Isotonic calibrator |
| `src/mfa_ml/explainability/shap_explainer.py` | TreeSHAP top-5 attributions |
| `src/mfa_ml/data/loader.py` | `FeatureExtractor` + domain-stratified split |
| `scripts/train.py` | Training CLI |
| `scripts/evaluate.py` | Holdout evaluation CLI |
| `artifacts/v1/` | Versioned model binaries + metrics |

## Classification output contract

Every score must include:

| Field | Values |
|-------|--------|
| `tier` | `MFA_High`, `MFA_Medium`, `MFA_Low`, `Non_MFA`, `Uncertain` |
| `mfa_score` | Calibrated 0–1 |
| `confidence` | `high`, `medium`, `low` |
| `top_signals` | Ranked feature contributions (max 5) |
| `explanation` | Template narrative citing signals |
| `evidence_hash` | Binds to signal snapshot for audit |
| `classifier` | `rules` or `xgboost` |
| `schema_version` | `v1` |

Tier mapping: [`../docs/DOMAIN.md`](../docs/DOMAIN.md)

## Local development

```bash
uv sync --all-packages

# Run worker (Postgres + artifacts required)
export DATABASE_URL=postgresql+asyncpg://mfa:mfa@localhost:5432/mfa
export ARTIFACT_DIR=ml/artifacts/v1
uv run --package mfa-ml python -m mfa_ml.worker
```

### Train model

```bash
uv run --package mfa-ml python ml/scripts/train.py \
  --db-url postgresql://mfa:mfa@localhost:5432/mfa \
  --gold-labels data/seed/gold_labels.jsonl \
  --artifact-dir ml/artifacts/v1
```

Outputs: `model.pkl`, `calibrator.pkl`, `metadata.json`, `training_summary.json`.

### Evaluate on holdout

```bash
uv run --package mfa-ml python ml/scripts/evaluate.py \
  --db-url postgresql://mfa:mfa@localhost:5432/mfa \
  --gold-labels data/seed/gold_labels.jsonl \
  --artifact-dir ml/artifacts/v1
```

Outputs: `metrics.json`. See `artifacts/v1/eval_notes.md` for pass/fail vs 85%/70% targets.

## Tests

```bash
# Unit tests (no Postgres)
uv run --package mfa-ml pytest ml/tests/ -q --ignore=ml/tests/test_consumer.py

# Integration (Postgres required)
MFA_RUN_INTEGRATION=1 uv run --package mfa-ml pytest ml/tests/test_consumer.py -v

# All
uv run --package mfa-ml pytest ml/tests/ -v
```

## Configuration

| Variable | Default | Purpose |
|----------|---------|---------|
| `DATABASE_URL` | (see root `.env`) | Async Postgres URL for score job poll |
| `ARTIFACT_DIR` | `ml/artifacts/v1` | Path to `model.pkl`, `calibrator.pkl`, `metadata.json` |
| `SCORE_POLL_INTERVAL_SEC` | `5` | Idle poll interval when queue is empty |
| `LOG_LEVEL` | `INFO` | JSON structured logs |
| `ENV` | `local` | Environment label |

In Docker Compose, `ARTIFACT_DIR=/artifacts` with `./ml/artifacts/v1:/artifacts:ro` volume mount.

## Targets (baseline milestone)

- Precision ≥ 85%, Recall ≥ 70% on gold-label holdout — **currently below target** (see `artifacts/v1/eval_notes.md`)
- Train/val split by **domain** (prevent leakage)
- Missing enrichment features → `null`, not `0`

Gold labels: [`../data/seed/`](../data/seed/)

## What's next

- **POC-5** — Full gold-label batch eval, confusion matrix report
- **TODO(MVP):** Feature expansion (dual-persona, refresh), LLM explanations, shadow mode, auto-retrain, S3 artifact loading

## Related docs

- [`../docs/SIGNALS.md`](../docs/SIGNALS.md) — `SignalFeatures` schema
- [`../backend/README.md`](../backend/README.md) — classifications API
- [`../crawler/README.md`](../crawler/README.md) — signal extraction
- [`.cursor/skills/mfa-classifier/SKILL.md`](../.cursor/skills/mfa-classifier/SKILL.md) — ML workflow skill
