# MFA Platform — Roadmap

Milestone definitions for **planning and scoping** only. Implementation code uses production-oriented names (`SignalFeatures`, `v1`, `ENV=local`) — see `AGENTS.md`.

## Baseline (6–8 weeks)

**In:** 5K–10K labeled URLs, single-persona crawl, ad density + content heuristics, rules + XGBoost, template explanations, basic reviewer workflow, Postgres only.

**Success:** Precision ≥85%, Recall ≥70%; explain top 5 signals.

**Out:** RAG bot, dual-persona, LLM explanations, OpenSearch.

## MVP (10–12 weeks after Baseline)

**In:** Dual-persona crawl + 60s refresh, batch + single-URL API, tiered classification + calibration, LLM explanations with citations, RAG v1, reviewer console, QuickSight dashboard, OpenSearch, Redis, audit v1.

**Out:** Sub-second pre-bid, mobile/CTV, auto-retraining, multi-tenant SaaS hardening.

## Production (12–16 weeks after MVP)

**In:** Near-real-time (&lt;5 min), pre-bid API, monthly auto-retrain, RAG v2 (similar domains, change detection), drift monitoring, shadow mode, SSO/RBAC, multi-region DR, cost attribution.

## Current default (2026-07-10)

**Baseline (POC) engineering exit complete.** **MVP implementation in progress** — dual-persona crawl, RAG v1, review console, Terraform infra.

| Phase | Status |
|-------|--------|
| P0 + POC-1 → POC-5 | ✅ Complete (metrics/crawl gaps documented) |
| **MVP** | 🟡 In progress — infra, RAG, review UI, HITL APIs |
| Production | Blocked on MVP exit |

**Plans:**
- Active sprint: [`docs/plans/2026-07-10-poc-5-exit.md`](plans/2026-07-10-poc-5-exit.md)
- MVP execution: [`docs/plans/2026-08-mvp-execution.md`](plans/2026-08-mvp-execution.md)
- Production: [`docs/plans/2026-11-production-execution.md`](plans/2026-11-production-execution.md)
- Multi-agent orchestration: [`.cursor/plans/multi-agent-execution-plan.md`](../.cursor/plans/multi-agent-execution-plan.md)

**Task breakdown:** [`docs/plans/2026-07-05-phased-build-plan.md`](plans/2026-07-05-phased-build-plan.md) — phased tasks with IDs (POC-* IDs are planning labels, not code prefixes).

Unless the user specifies otherwise, implement **POC-5** scope. Do not start MVP until POC exit checklist passes.

## Open plan todos

1. ~~Validate gold-label URL dataset with Ad Ops~~ — automated validation done; formal sign-off pending
2. ~~Playwright crawler on 100 domains~~ — POC-2.5 done (84% success)
3. ~~Signal feature schema + Postgres JSONB~~ — `SignalFeatures` in `schemas/signals.py`, `docs/SIGNALS.md`
4. ~~Train rules + XGBoost~~ — artifacts in `ml/artifacts/v1/`; precision/recall gap documented — remediate in MVP-2.1
5. ~~**POC-5** — batch eval, list classifications API, reviewer CSV, OpenAPI polish~~ — **Done** (2026-07-10)
6. RAG bot v1 with hybrid retrieval + citation validator — MVP (`docs/plans/2026-08-mvp-execution.md`)
7. Reviewer console with override workflow + audit logging — MVP
8. Shadow-mode scoring before blocklist export — MVP
