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
| Containers | `*/Dockerfile`, `docker-compose.yml`, `.dockerignore` | `mfa-docker.mdc` |
| UI | `frontend/src/` | `mfa-review-ui.mdc` |

## Current milestone: MVP (Baseline exit complete 2026-07-10)

**Done:** P0, POC-1 → POC-5 (batch eval in `ml/artifacts/v1/batch_eval_report.json`)  
**Next:** MVP-1 per `docs/plans/2026-08-mvp-execution.md`

| Sprint doc | Focus |
|------------|-------|
| `docs/plans/2026-07-10-poc-5-exit.md` | Current — API + batch eval |
| `docs/plans/2026-08-mvp-execution.md` | Dual-persona, RAG, review UI |
| `docs/plans/2026-11-production-execution.md` | NRT, MLOps, enterprise |

**Orchestration:** `.cursor/plans/multi-agent-execution-plan.md`  
Full HLD: `.cursor/plans/mfa_platform_architecture_48645023.plan.md`

## Agent routing (quick)

| Work type | Agent |
|-----------|-------|
| Phase / sprint planning | `mfa-platform-orchestrator` |
| API, workers, audit | `mfa-backend-engineer` |
| Crawler, DOM, personas | `mfa-crawler-engineer` |
| Train, eval, scoring | `mfa-ml-engineer` |
| RAG, chat, OpenSearch | `mfa-rag-engineer` |
| Review / bot UI | `mfa-review-ui-engineer` |
| Terraform, AWS, compose | `mfa-infra-engineer` |
| ADRs, scope gates | `mfa-architect` |
| AI/auth audit gate | `mfa-security-reviewer` |

## Docker optimization

When changing images or Compose: skill **`mfa-docker`** · rule **`mfa-docker.mdc`**.

Key constraints: repo-root build context · `uv sync --frozen --no-dev` · crawler stays on `python:3.12-slim-bookworm` (Playwright) · pin `uv` version · exclude `data/` and `ml/artifacts/` from context.
