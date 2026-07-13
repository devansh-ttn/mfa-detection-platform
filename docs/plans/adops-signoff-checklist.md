# Ad Ops Sign-Off Checklist

**Phase:** Baseline exit → MVP kickoff  
**Status:** Pending external approval  
**Related:** [`data/seed/README.md`](../../data/seed/README.md), [`ml/artifacts/v1/eval_notes.md`](../../ml/artifacts/v1/eval_notes.md)

---

## Batch eval findings (2026-07-10)

| Gate | Result | Action |
|------|--------|--------|
| Crawl success ≥90% | 46.0% (283/615) | Refresh seed URLs — 215 synthetic 404s |
| Precision ≥85% | 18.9% | MVP-2.1 feature expansion + tier recalibration |
| Recall ≥70% | 55.2% | MVP-2.1 retrain on refreshed labels |

Run unreachable URL audit:

```bash
uv run python scripts/seed/audit_unreachable_urls.py \
  --output data/seed/unreachable_urls.csv
```

---

## Sign-off checklist

### 1. Gold-label quality review

- [ ] Stratified sample review (50 URLs: 25 MFA_High, 25 Non_MFA)
- [ ] Replace or remove URLs in `data/seed/unreachable_urls.csv`
- [ ] Confirm subdomain vs parent-domain labels (e.g. `za.investing.com` vs `www.investing.com`)
- [ ] Re-run batch eval after refresh; target ≥90% crawl success

### 2. Explanation quality review

- [ ] Export reviewer CSV: `uv run python scripts/export/reviewer_csv.py`
- [ ] Ad Ops reviews 20 sample explanations (10 MFA_High, 10 Non_MFA)
- [ ] Document false-positive patterns for tier threshold tuning

### 3. DSP inventory overlap

- [ ] Confirm ≥30% of seed domains appear in active DSP inventory feeds
- [ ] Document inventory source and date range

### 4. Formal approval

```
Reviewer name:
Role:
Date:
Decision: [ ] Approved for MVP pilot  [ ] Approved with conditions  [ ] Rejected

Conditions / notes:


Signature (email):
```

---

## Post-sign-off actions

1. Update `data/seed/manifest.json` version if labels change
2. Re-run `scripts/seed/validate_gold_labels.py`
3. Re-run full batch pipeline per `LOCAL_DEV_GUIDE` §7.14
4. Orchestrator marks Ad Ops gate complete in sprint planning
