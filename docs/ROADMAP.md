# MFA Platform — Roadmap

## POC (6–8 weeks)

**In:** 5K–10K labeled URLs, single-persona crawl, ad density + content heuristics, rules + XGBoost, template explanations, basic reviewer UI, Postgres only.

**Success:** Precision ≥85%, Recall ≥70%; explain top 5 signals.

**Out:** RAG bot, dual-persona, LLM explanations, OpenSearch.

## MVP (10–12 weeks after POC)

**In:** Dual-persona crawl + 60s refresh, batch + single-URL API, tiered classification + calibration, LLM explanations with citations, RAG v1, reviewer console, QuickSight dashboard, OpenSearch, Redis, audit v1.

**Out:** Sub-second pre-bid, mobile/CTV, auto-retraining, multi-tenant SaaS hardening.

## Production (12–16 weeks after MVP)

**In:** Near-real-time (&lt;5 min), pre-bid API, monthly auto-retrain, RAG v2 (similar domains, change detection), drift monitoring, shadow mode, SSO/RBAC, multi-region DR, cost attribution.

## Current default

Unless the user specifies otherwise, implement **POC scope** first. Reference `.cursor/plans/mfa_platform_architecture_48645023.plan.md` for full detail.

## Open plan todos

1. Validate gold-label URL dataset with Ad Ops
2. POC spike: dual-persona crawler on 100 known MFA/non-MFA domains
3. Finalize signal feature schema + Postgres JSONB design
4. Train rules + XGBoost; target precision ≥85%, recall ≥70%
5. RAG bot v1 with hybrid retrieval + citation validator
6. Reviewer console with override workflow + audit logging
7. MVP pilot: shadow-mode scoring before blocklist export
