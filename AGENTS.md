# AGENTS.md — MFA Detection Platform

Context for humans and coding agents working on the **Made-For-Advertising (MFA) detection platform**.

## Mission

Build a **multi-signal, hybrid ML + LLM system** that ingests ad-inventory URLs, extracts page-level evidence via headless crawling, scores MFA risk with calibrated confidence, explains decisions with cited signals, routes uncertain cases to human reviewers, and exposes a **RAG bot** grounded in structured signals and policy corpora.

**Core principle:** Score at **URL/page-section granularity** (not domain-only). Store **versioned evidence snapshots** for audit and RAG grounding. Combine crawl + traffic + programmatic metadata — no single signal is sufficient.

## Stack

See `.cursor/rules/mfa-core.mdc` for the full stack. Summary:
Python 3.12+ · FastAPI · Playwright · XGBoost/LightGBM · Postgres JSONB · OpenSearch · Redis · S3 · AWS · React+TypeScript · **uv** workspace · Docker Compose

## Repository layout

```
mfa-detection-platform/
├── AGENTS.md               # This file
├── docker-compose.yml      # Local orchestration
├── pyproject.toml          # uv workspace root
├── docs/                   # ARCHITECTURE · DOMAIN · ADRS · SIGNALS · RAG · ROADMAP · GUARDRAILS
│   └── plans/              # Phased build plan (2026-07-05-phased-build-plan.md)
├── common/                 # mfa-common — shared logging
├── backend/                # FastAPI ingestion + scoring API
├── crawler/                # Playwright crawl worker
├── ml/                     # Rules + XGBoost scoring
├── data/seed/              # 615 gold-labelled URLs
└── infra/terraform/        # AWS resources (planned)
```

Local dev & manual testing: **`docs/LOCAL_DEV_GUIDE.md`**

## Agent workflow

1. **Read first:** `docs/ARCHITECTURE.md`, `docs/DOMAIN.md`, `docs/ROADMAP.md` — know current milestone scope
2. **ADRs:** `docs/ADRS.md` before changing model, vector store, or orchestration choices
3. **Signals:** `docs/SIGNALS.md` before adding/changing feature schema
4. **RAG:** `docs/RAG.md` before bot or retrieval changes
5. **Security:** `docs/GUARDRAILS.md` + `.cursor/rules/mfa-security.mdc` for all AI-facing code
6. **Cursor rules:** `.cursor/rules/mfa-*.mdc` — follow stack and layer conventions
7. **Skills:** `.cursor/skills/` — use domain workflows for classifier, crawler, RAG, ADRs, Docker
8. **Containers:** `.cursor/skills/mfa-docker/SKILL.md` + `.cursor/rules/mfa-docker.mdc` when changing Dockerfiles, Compose, or `.dockerignore`
9. **Plans:** save implementation plans to `.cursor/plans/` or `docs/plans/YYYY-MM-DD-<feature>.md`

### Branch + verify before commit

Work on a **phase branch** (e.g. `cursor/poc-4-workers`), not `main`/`develop` directly.

When a phase task is done:

1. **Unit tests** (integration auto-skipped without `MFA_RUN_INTEGRATION=1`):
   ```bash
   uv run --package mfa-backend pytest backend/tests/ -q
   uv run --package mfa-ml pytest ml/tests/ -q
   uv run --package mfa-crawler pytest crawler/tests/ -q -m "not integration"
   ```
2. **Integration** (optional; Postgres on `:5432`): `MFA_RUN_INTEGRATION=1 uv run --package mfa-backend pytest backend/tests/ -q`
3. **Commit** on the phase branch (Conventional Commits, state *why*). No `.env`, pickles, or credentials.
4. Open PR into `develop` when phase exit criteria pass.

## Milestone scope

| Milestone | Duration | Key deliverables |
|-----------|----------|-----------------|
| **Baseline** | 6–8 wk | Single-persona crawl, rules + XGBoost, template explanations, Postgres, ingestion + signals API |
| **MVP** | +10–12 wk | Dual-persona crawl, LLM explanations, RAG v1, review console, OpenSearch, Redis, audit v1 |
| **Production** | +12–16 wk | Near-real-time path, pre-bid API, auto-retrain, RAG v2, SSO/RBAC, multi-region DR |

**Do not implement Production-only features unless explicitly requested.** Check `docs/ROADMAP.md` before adding MVP/Production capabilities.

## Patterns (critical)

- **Retrieve-first RAG:** No generation without evidence pack; citation validator on every claim
- **LLM scope:** Explanation + RAG only — never primary MFA classifier (ADR-001)
- **Dual-persona crawl:** Direct + simulated Outbrain/Taboola referrer — TODO(MVP)
- **Versioned signals:** `signals_v{n}` per `url_id`; never overwrite without version bump
- **HITL:** Override stores `final_label` + `override_reason`; does not delete ML score
- **Async workers:** Crawl and LLM calls off the hot API path

## Do not

- LLM-only classification (ADR-001) · domain-only scoring · homepage-only crawl
- Trust viewability or IVT as sole MFA signals
- Skip audit trail on scores, overrides, or RAG answers
- Commit `.env`, credentials, or production keys
- Add dependencies without justification in change summary
