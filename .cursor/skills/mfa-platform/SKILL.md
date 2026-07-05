---
name: mfa-platform
description: Navigates the MFA detection platform architecture, docs, phases, and ADRs. Use when starting work on this repo, scoping features to POC/MVP/Production, or understanding system components, data flow, and integration points.
---

# MFA Platform Navigation

## Quick start

1. Read `AGENTS.md` for mission, stack, and workflow
2. Local stack: `docker compose up -d` from **repo root** (`docker-compose.yml`)
3. Check `docs/ROADMAP.md` for current phase scope
3. Read layer-specific docs before coding:
   - Architecture → `docs/ARCHITECTURE.md`
   - Domain terms → `docs/DOMAIN.md`
   - Decisions → `docs/ADRS.md`
   - Features → `docs/SIGNALS.md`
   - RAG → `docs/RAG.md`
   - Security → `docs/GUARDRAILS.md`

## Phase gating

| User asks for… | Default unless stated |
|----------------|----------------------|
| Crawler, scoring, UI | POC scope first |
| RAG bot, dual-persona, LLM explanations | MVP scope |
| Pre-bid API, auto-retrain, multi-region | Production scope |

Flag scope creep: "This is an MVP feature — confirm before implementing."

## Layer → path mapping

| Layer | Code path (target) | Rule | Agent |
|-------|-------------------|------|-------|
| Ingestion/API | `backend/src/mfa/` | `mfa-api.mdc` | — |
| Crawler | `crawler/src/` | `mfa-crawler.mdc` | `mfa-crawler-engineer` |
| ML/Scoring | `ml/src/` | `mfa-ml-scoring.mdc` | `mfa-ml-engineer` |
| Shared | `common/src/mfa_common/` | `mfa-core.mdc` | — |
| RAG | `backend/src/mfa/rag/` | `mfa-rag.mdc` | `mfa-rag-engineer` |
| Infra | `infra/terraform/` | `mfa-infra-aws.mdc` | — |
| UI | `frontend/src/` | `mfa-review-ui.mdc` | `mfa-review-ui-engineer` |

## Full architecture plan

Detailed HLD: `.cursor/plans/mfa_platform_architecture_48645023.plan.md`
