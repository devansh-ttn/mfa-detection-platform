# Shadow Mode Runbook (MVP-5.1)

Score and classify inventory **without enforcing blocks** for 4 weeks before enabling blocklist export.

## Prerequisites

- MVP scoring pipeline live (dual-persona crawl optional)
- `GET /api/v1/blocklist` available but **not** wired to DSP enforcement
- Ad Ops sign-off checklist started

## Procedure

### Week 1 — Baseline shadow

1. Ingest DSP inventory: `uv run python scripts/ingest/dsp_inventory.py --file inventory.csv`
2. Run workers: `docker compose up -d`
3. Export shadow blocklist daily:
   ```bash
   curl -s "http://localhost:8000/api/v1/blocklist?tier=MFA_High&limit=1000" | jq '.total'
   ```
4. Compare shadow MFA_High domains against Ad Ops manual review sample (50 URLs)

### Week 2–3 — Metrics review

1. Track precision/recall on reviewer-validated subset
2. Review false positives via `GET /api/v1/reviews/queue`
3. Submit overrides: `POST /api/v1/reviews` with `override_reason`
4. Re-run `scripts/eval/batch_pipeline_report.py --report-only` after threshold tuning

### Week 4 — Go/no-go

| Gate | Target |
|------|--------|
| Shadow precision (reviewer sample) | ≥85% |
| False positive rate on top publishers | <5% |
| Reviewer SLA | 24h for uncertain high-spend URLs |
| Security review | MVP-5.4 complete (`docs/security/aws-deployment-checklist.md`) |

**Metrics helper:**

```bash
# Daily export (cron)
./scripts/shadow/daily_blocklist_export.sh

# Weekly rollup
uv run python scripts/shadow/shadow_metrics.py --week 2
```

Set `MFA_SHADOW_MODE=1` on API until Ad Ops approves DSP enforcement. Blocklist responses include `"shadow_mode": true`.

**Go:** Enable blocklist push to DSP.  
**No-go:** Extend shadow 2 weeks; tune MVP-2.2 thresholds.

## Rollback

- Disable DSP blocklist webhook
- Keep scoring in shadow (classifications still written for audit)
