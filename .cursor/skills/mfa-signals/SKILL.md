---
name: mfa-signals
description: Defines and extends MFA signal feature schema, Postgres JSONB storage, and evidence artifacts. Use when adding features, designing signal_snapshots tables, parsing DOM metrics, or working with the ~40-60 feature vector.
---

# MFA Signal Features

## Reference

`docs/SIGNALS.md` — canonical feature list and storage conventions.

## Workflow: add a new signal

```
Task Progress:
- [ ] Confirm signal tier (1/2/3) and gaming risk in docs/SIGNALS.md
- [ ] Add field to feature schema with type, range, and null semantics
- [ ] Implement extractor in crawler or enrichment worker
- [ ] Add to Postgres JSONB schema migration
- [ ] Update ML training pipeline feature list
- [ ] Add SHAP attribution support if used in explanations
```

## Naming conventions

- Ratios: `_ratio` suffix, 0–1
- Percentages: `_pct` suffix, 0–100
- Counts: `_count` suffix, non-negative int
- Booleans: `_exists` suffix

## Postgres pattern

```sql
-- signal_snapshots: url_id, version, crawl_ts, persona, signals JSONB, evidence_s3_prefix
```

Never update in place — insert new version row.

## Evidence linkage

Every snapshot references S3 prefix: `evidence/{url_id}/{version}/`

Compute `evidence_hash` from canonical JSON of `signals` + artifact checksums.

## Tier 1 signals (prioritize)

Ad density, refresh behavior, traffic skew, referral/direct delta, content quality.
