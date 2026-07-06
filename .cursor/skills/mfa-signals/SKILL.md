---
name: mfa-signals
description: Defines and extends MFA signal feature schema, Postgres JSONB storage, and evidence artifacts. Use when adding features, designing signal_snapshots tables, parsing DOM metrics, or working with the feature vector.
---

# MFA Signal Features

## Reference

`docs/SIGNALS.md` — canonical feature list and storage conventions.  
`backend/src/mfa/schemas/signals.py` — `SignalFeatures`, `SignalSnapshotPayload`, `compute_evidence_hash`.

## Workflow: add a new signal

```
Task Progress:
- [ ] Confirm signal tier (1/2/3) and gaming risk in docs/SIGNALS.md
- [ ] Add field to SignalFeatures (or ENRICHMENT_FEATURE_NAMES if enrichment-only)
- [ ] Bump schema_version if breaking; document migration in SIGNALS.md
- [ ] Implement extractor in crawler or enrichment worker
- [ ] Update ML training pipeline feature list
- [ ] Add SHAP attribution support if used in explanations
```

## Naming conventions

- Ratios: `_ratio` suffix, 0–1
- Percentages: `_pct` suffix, 0–100
- Counts: `_count` suffix, non-negative int
- Booleans: `_exists` suffix
- **No** `POC_` / `Mvp_` prefixes on types or constants

## Postgres pattern

```sql
-- signal_snapshots: url_id, version, persona, signals JSONB, evidence_hash, crawl_duration_sec
```

JSONB document: `schema_version`, `crawl_ts`, plus flat `SignalFeatures` keys.

Never update in place — insert new version row.

## Evidence linkage

Local dev: `backend/evidence/{url_id}/{version}/`  
Deployed: `s3://{bucket}/evidence/{url_id}/{version}/` (TODO(MVP))

Compute `evidence_hash` = SHA-256 of canonical JSON of `signals` (see `compute_evidence_hash`).

## Tier 1 signals (prioritize)

Ad density, refresh behavior, traffic skew, referral/direct delta, content quality.

Enrichment-only fields live in `ENRICHMENT_FEATURE_NAMES` until MVP workers ship.
