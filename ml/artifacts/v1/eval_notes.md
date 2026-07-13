# POC-5.4 Evaluation Notes — Live Batch Run

**Evaluated:** 2026-07-10  
**Artifact:** `ml/artifacts/v1/`  
**Batch report:** `ml/artifacts/v1/batch_eval_report.json`  
**Eval set:** 283 URLs with successful crawl + classification (of 615 gold labels)

## POC exit summary

| Gate | Result | Status |
|------|--------|--------|
| Crawl success ≥90% | **46.0%** (283/615) | **Not met** — documented below |
| Precision ≥85% | **18.9%** | **Not met** — documented below |
| Recall ≥70% | **55.2%** | **Not met** — documented below |
| Full output contract | All 284 classifications | **Met** |
| Async crawl→score | Workers E2E | **Met** |
| Audit trail | Per classification | **Met** |
| Ad Ops sign-off | — | **Pending** (external) |

**Decision:** POC-5 engineering tasks are **complete**. Baseline exit proceeds with **documented gaps**; remediation tracked in MVP-2.1 (feature expansion) and seed-data refresh with Ad Ops.

---

## Batch pipeline (POC-5.3)

| Metric | Value |
|--------|-------|
| Gold labels ingested | 615 |
| Crawl completed | 283 |
| Crawl failed | 332 |
| Crawl success rate | 46.0% |
| Score success rate | 100% (283/283 completed crawls) |
| Snapshot coverage | 46.18% |
| Classification coverage | 46.18% |
| Wait time | ~44 min (single crawler worker) |

### Crawl failure breakdown

| Error type | Count |
|------------|-------|
| `not_found` (HTTP 404) | 215 |
| `http_error` | 73 |
| `unknown` (DNS / network) | 41 |
| `timeout` | 3 |

**Root cause (crawl):** A large fraction of gold-label URLs are synthetic seed entries pointing at fabricated paths on real domains (e.g. `economist.com/world/`, `sciencepicker.com/...`) or non-resolving hosts. These fail permanently at crawl time — not a worker or pipeline defect. Score pipeline succeeded on every completed crawl.

---

## Live + model evaluation (POC-5.4)

Evaluated on **283 crawled samples** (all with snapshots + classifications).

| Metric | Live pipeline | Model (all crawled) |
|--------|---------------|---------------------|
| Precision | 18.9% | 18.9% |
| Recall | 55.2% | 55.2% |
| F1 | 28.2% | 28.2% |
| TP / FP / FN / TN | 32 / 137 / 26 / 88 | 32 / 137 / 26 / 88 |

### Tier breakdown (predicted vs gold)

| Tier | Gold MFA | Gold Non_MFA |
|------|----------|--------------|
| `MFA_High` | 32 | 128 |
| `MFA_Medium` | 0 | 9 |
| `Non_MFA` | 26 | 88 |

### Root causes (metrics)

1. **High false-positive rate** — `MFA_High` tier fires on 128 Non_MFA gold labels; rules/XGBoost over-index on ad-density with only 5 populated crawl features.
2. **Sparse feature coverage** — 11 of 16 schema fields remain `null`; refresh and enrichment signals deferred to MVP.
3. **Training/eval domain skew** — Model trained on earlier 281-URL subset; batch adds new domains with different DOM profiles.
4. **Conservative MFA_Medium** — Zero MFA gold labels predicted as `MFA_Medium`; threshold tuning needed.

---

## Remediation plan (MVP)

1. **Seed data refresh** — Ad Ops review of gold labels; replace synthetic 404 URLs with live inventory samples (target ≥90% crawl success).
2. **MVP-1.4 / MVP-1.5** — Dual-persona crawl + 60s refresh detection.
3. **MVP-2.1** — Expand to 40–60 features; retrain on refreshed labels.
4. **MVP-2.2** — Recalibrate tier thresholds; reduce `MFA_High` false positives on legitimate publishers.
5. Re-run `scripts/eval/batch_pipeline_report.py --report-only` after MVP-2.

---

## Commands used

```bash
# Ingest full gold-label set
uv run python scripts/seed/ingest_gold_labels.py --source-batch-id poc-5-batch-eval

# Wait + report + evaluate (workers must be running)
uv run --package mfa-ml python scripts/eval/batch_pipeline_report.py --wait --timeout 7200

# Reviewer export for HITL
uv run --package mfa-backend python scripts/export/reviewer_csv.py --output reviewer_queue.csv
```
