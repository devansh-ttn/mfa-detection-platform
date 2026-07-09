# POC-3.7 Evaluation Notes

**Evaluated:** 2026-07-08  
**Artifact:** `ml/artifacts/v1/`  
**Holdout:** 61 samples (domain-stratified, 20% of 281 crawled gold-label URLs)

## Result: FAIL

| Metric | Result | Target |
|--------|--------|--------|
| Precision | 0.0% | ≥ 85% |
| Recall | 0.0% | ≥ 70% |
| F1 | 0.0% | — |

**Confusion matrix:** TP=0, FP=3, FN=12, TN=46

## Root causes

1. **Sparse feature coverage** — Only 5 of 16 schema features are populated by the Baseline crawler; 11 enrichment/refresh fields remain `null`.
2. **Incomplete crawl coverage** — 281/615 gold URLs have snapshots (334 skipped); model trained on subset.
3. **Tier mapping conservatism** — Most MFA gold labels land in `Uncertain` (4) or `Non_MFA` (8) tiers; zero true MFA samples predicted as `MFA_High` or `MFA_Medium`.
4. **Rules engine** — 0% precision/recall on validation (56% coverage); rules short-circuit does not improve holdout.

## Remediation plan (MVP)

1. Crawl remaining gold-label URLs (target ≥90% success rate per POC-5.3).
2. Add dual-persona crawl + 60s refresh detection (MVP-1.4, MVP-1.5) to populate deferred features.
3. Tune rules thresholds and tier cut-offs on expanded feature set.
4. Re-train after feature expansion; re-run `ml/scripts/evaluate.py`.

## Decision

Proceed with POC-4 pipeline wiring per baseline plan — metrics gap is documented, not a blocker for async score worker integration.
