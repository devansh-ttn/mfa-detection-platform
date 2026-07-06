---
name: mfa-classifier
description: Trains and deploys the MFA rules + XGBoost ensemble with confidence calibration and tier mapping. Use when building scoring service, training pipelines, evaluating precision/recall, or generating SHAP attributions.
---

# MFA Classifier

## Reference

`docs/ADRS.md` (ADR-001, ADR-002) · `docs/SIGNALS.md` · `backend/src/mfa/schemas/signals.py` · `.cursor/rules/mfa-ml-scoring.mdc`

## Pipeline

```
1. Rules engine (deterministic high-confidence patterns)
2. XGBoost/LightGBM on remaining URLs
3. Platt scaling or isotonic calibration → confidence
4. Tier mapper (score + confidence → MFA_High/Medium/Low/Non_MFA/Uncertain)
5. Template explanation (current) — TODO(MVP): LLM explanations with citations
```

## Baseline success criteria

- Precision ≥ 85%, Recall ≥ 70% on gold labels (`docs/ROADMAP.md`)
- Explain top 5 signals per classification

## Training rules

- Domain-level train/val split (prevent leakage)
- Document feature schema version (`v1`) in model metadata
- Store metrics + confusion matrix per training run

## Rules engine examples

| Rule | Condition | Tier |
|------|-----------|------|
| High ad density + refresh | `ad_to_content_ratio > 0.3` AND `refresh_events_60s >= 3` | MFA_High |
| Referral delta | `referral_direct_delta_score > threshold` | MFA_Medium |

> `referral_direct_delta_score` requires dual-persona crawl — TODO(MVP).

## Output

Persist to `classifications` table with `top_signals` JSON for RAG and UI.

## Do not

Use LLM output as `tier` label.
