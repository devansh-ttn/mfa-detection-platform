# mfa-ml

Rules engine + gradient-boosted classifier for MFA risk scoring. Runs as a **worker** off the API hot path.

## Purpose

After the crawler extracts DOM signals into `signal_snapshots`, the ML worker loads those features, runs a **rules engine** and **XGBoost/LightGBM ensemble**, calibrates confidence, maps to an MFA tier, and writes a `classifications` row with `top_signals` and a template explanation.

**Important:** LLM is not used for classification (see ADR-001). LLM is reserved for explanations and RAG in later milestones.

## Target workflow

```
signal_snapshots (Postgres)  -->  ml-worker  -->  classifications
                                        |
                              rules -> XGBoost -> calibrator -> tier
                                        |
                              top_signals + explanation
```

1. **Dequeue** — Pick up a score job (after crawl completes).
2. **Load** — Read latest `SignalSnapshot` JSONB for the URL.
3. **Score** — Rules engine catches high-confidence patterns; ensemble ranks risk; calibrator sets confidence.
4. **Explain** — Template explanation citing `top_signals` only (no LLM in baseline).
5. **Persist** — Insert `classifications` row; append audit event.

## Current state

The **`ml-worker`** is a **stub** — it logs readiness and sleeps in a loop. Rules, training, and the score consumer are planned in the build plan (POC-3 / POC-4).

```bash
docker compose --profile workers up -d ml-worker
docker compose logs -f ml-worker
```

## Planned layout

| Path | Role |
|------|------|
| `src/mfa_ml/worker.py` | Score queue consumer (stub) |
| `src/mfa_ml/rules/` | High-confidence MFA patterns (planned) |
| `src/mfa_ml/ensemble/` | XGBoost/LightGBM model (planned) |
| `src/mfa_ml/calibration/` | Platt / isotonic calibrator (planned) |
| `scripts/train.py` | Training CLI (planned) |
| `artifacts/` | Versioned model + metrics JSON (planned) |

## Classification output contract

Every score must include:

| Field | Values |
|-------|--------|
| `tier` | `MFA_High`, `MFA_Medium`, `MFA_Low`, `Non_MFA`, `Uncertain` |
| `mfa_score` | Calibrated 0–1 |
| `confidence` | `high`, `medium`, `low` |
| `top_signals` | Ranked feature contributions |
| `explanation` | Template narrative citing signals |
| `evidence_hash` | Binds to signal snapshot for audit |

Tier mapping: [`../docs/DOMAIN.md`](../docs/DOMAIN.md)

## Local development

```bash
uv sync --all-packages

# Run worker stub
uv run --package mfa-ml python -m mfa_ml.worker
```

Tests and training scripts will be added with POC-3.

## Targets (baseline milestone)

- Precision ≥ 85%, Recall ≥ 70% on gold-label holdout
- Train/val split by **domain** (prevent leakage)
- Missing enrichment features → `null`, not `0`

Gold labels: [`../data/seed/`](../data/seed/)

## What's next

- **POC-3** — Rules engine, XGBoost training, tier mapper, template explanations
- **POC-4** — `score_consumer` wired to queue, classifications API
- **TODO(MVP):** LLM explanations, shadow mode, auto-retrain

## Related docs

- [`../docs/SIGNALS.md`](../docs/SIGNALS.md) — `SignalFeatures` schema
- [`../crawler/README.md`](../crawler/README.md) — signal extraction
- [`.cursor/skills/mfa-classifier/SKILL.md`](../.cursor/skills/mfa-classifier/SKILL.md) — ML workflow skill
