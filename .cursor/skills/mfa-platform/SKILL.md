---
name: mfa-platform
description: Navigates the MFA detection platform architecture, docs, phases, and ADRs. Use when starting work on this repo, scoping features against the roadmap, or understanding system components, data flow, and integration points.
---

# MFA Platform Navigation

## Quick start

1. Read `AGENTS.md` for mission, stack, and workflow
2. Local stack: `docker compose up -d` from **repo root** (`docker-compose.yml`)
3. Check `docs/ROADMAP.md` and `docs/plans/2026-07-05-phased-build-plan.md` for milestone scope
4. Read layer-specific docs before coding:
   - Architecture → `docs/ARCHITECTURE.md`
   - Domain terms → `docs/DOMAIN.md`
   - Decisions → `docs/ADRS.md`
   - Features → `docs/SIGNALS.md`
   - RAG → `docs/RAG.md`
   - Security → `docs/GUARDRAILS.md`

## Implementation naming (required)

| Do | Don't |
|----|-------|
| `SignalFeatures`, `schema_version: v1` | `POCFeatureSignals`, `poc-v1` in new code |
| `TODO(MVP):` / `TODO(Production):` in code | Phase labels in class or module names |
| `ENV=local` for Compose | `ENV=poc` |
| Gate scope via `docs/ROADMAP.md` | Embed milestone names in APIs/schemas |

Canonical types: `backend/src/mfa/schemas/signals.py`

## Milestone gating

Scope is defined in **`docs/ROADMAP.md`** — not in code prefixes. Before implementing:

| Capability | Roadmap milestone |
|------------|-------------------|
| Single-persona crawl, rules + XGBoost, template explanations | Baseline (current) |
| Dual-persona, LLM explanations, RAG, review console | MVP |
| Pre-bid API, auto-retrain, multi-region | Production |

Flag scope creep: "This is an MVP feature — confirm before implementing."

## Layer → path mapping

| Layer | Code path | Rule | Agent |
|-------|-----------|------|-------|
| Ingestion/API | `backend/src/mfa/` | `mfa-api.mdc` | — |
| Crawler | `crawler/src/` | `mfa-crawler.mdc` | `mfa-crawler-engineer` |
| ML/Scoring | `ml/src/` | `mfa-ml-scoring.mdc` | `mfa-ml-engineer` |
| Shared | `common/src/mfa_common/` | `mfa-core.mdc` | — |
| RAG | `backend/src/mfa/rag/` | `mfa-rag.mdc` | `mfa-rag-engineer` |
| Infra | `infra/terraform/` | `mfa-infra-aws.mdc` | — |
| UI | `frontend/src/` | `mfa-review-ui.mdc` | `mfa-review-ui-engineer` |

## Full architecture plan

Detailed HLD: `.cursor/plans/mfa_platform_architecture_48645023.plan.md`
