---
name: mfa-platform
description: Navigates the MFA detection platform architecture, docs, phases, and ADRs. Use when starting work on this repo, scoping features against the roadmap, or understanding system components, data flow, and integration points.
---

# MFA Platform Navigation

## Quick start

1. Read `AGENTS.md` — mission, stack, agent workflow
2. Local stack: `docker compose up -d` from **repo root**; see `docs/LOCAL_DEV_GUIDE.md`
3. Gate scope: `docs/ROADMAP.md` + `docs/plans/2026-07-05-phased-build-plan.md`
4. Layer docs before coding: `docs/ARCHITECTURE.md` · `docs/DOMAIN.md` · `docs/ADRS.md` · `docs/SIGNALS.md` · `docs/RAG.md` · `docs/GUARDRAILS.md`

## Layer → path → rule

| Layer | Code path | Rule file |
|-------|-----------|-----------|
| Ingestion/API | `backend/src/mfa/` | `mfa-api.mdc` |
| Crawler | `crawler/src/` | `mfa-crawler.mdc` |
| ML/Scoring | `ml/src/` | `mfa-ml-scoring.mdc` |
| Shared | `common/src/mfa_common/` | `mfa-core.mdc` |
| RAG | `backend/src/mfa/rag/` | `mfa-rag.mdc` |
| Infra | `infra/terraform/` | `mfa-infra-aws.mdc` |
| UI | `frontend/src/` | `mfa-review-ui.mdc` |

## Current milestone: Baseline

Single-persona crawl · rules + XGBoost · template explanations · Postgres · ingestion + signals API
Dual-persona / LLM / RAG / review console → **MVP** (flag scope creep before implementing)

Full HLD: `.cursor/plans/mfa_platform_architecture_48645023.plan.md`
