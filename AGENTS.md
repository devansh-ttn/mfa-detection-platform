# AGENTS.md — MFA Detection Platform

Context for humans and coding agents (including Cursor) working on the **Made-For-Advertising (MFA) detection platform**.

## Mission

Build a **multi-signal, hybrid ML + LLM system** that ingests ad-inventory URLs, extracts page-level evidence via headless crawling, scores MFA risk with calibrated confidence, explains decisions with cited signals, routes uncertain cases to human reviewers, and exposes a **RAG bot** grounded in structured signals and policy corpora.

**Core principle:** Score at **URL/page-section granularity** (not domain-only). Store **versioned evidence snapshots** for audit and RAG grounding. Combine crawl + traffic + programmatic metadata — no single signal is sufficient.

## Stack (planned)


| Layer           | Technology                                                                         |
| --------------- | ---------------------------------------------------------------------------------- |
| API             | FastAPI (async), API Gateway, OpenAPI                                              |
| Crawler         | Playwright cluster (dual-persona: direct + referral referrer)                      |
| ML              | Rules engine + XGBoost/LightGBM ensemble + confidence calibrator                   |
| LLM             | Bedrock (Claude) or Azure OpenAI — explanations + RAG only, not primary classifier |
| Signal store    | PostgreSQL 16 (JSONB feature vectors)                                              |
| Vector / search | OpenSearch Serverless (hybrid BM25 + k-NN)                                         |
| Cache           | Redis (hot domain tier + explanation cache)                                        |
| Artifacts       | S3 (screenshots, HTML, parquet)                                                    |
| Orchestration   | SQS priority queues, Step Functions (batch), ECS Fargate (crawler workers)         |
| Audit           | DynamoDB + S3 Object Lock (immutable trail)                                        |
| Web             | Vite + React + TypeScript (reviewer console + bot UI)                              |
| Dashboards      | QuickSight (ops metrics)                                                           |
| Cloud           | **AWS primary** (Azure/GCP equivalents documented)                                 |
| Tooling         | **uv** (workspace root) · **npm** (`frontend/`)                                    |
| Local runtime   | **Docker Compose** at repo root — one container per service                          |




## Repository layout (target)

```
mfa-detection-platform/
├── AGENTS.md                      # This file — agent entry point
├── README.md
├── pyproject.toml                 # uv workspace root
├── uv.lock                        # Single lockfile for all Python packages
├── docker-compose.yml             # Local dev — all services (root level)
├── .env.example                   # Compose env vars (copy to .env)
├── .dockerignore
├── docs/
│   ├── ARCHITECTURE.md            # System components & data flow
│   ├── DOMAIN.md                  # MFA terminology & tier taxonomy
│   ├── ADRS.md                    # Architecture decision records
│   ├── SIGNALS.md                 # Feature schema (~40–60 features)
│   ├── RAG.md                     # RAG bot design & response contract
│   ├── ROADMAP.md                 # Milestone scope (Baseline → MVP → Production)
│   └── GUARDRAILS.md              # Risk controls & compliance defaults
├── .cursor/
│   ├── rules/                     # mfa-*.mdc project rules
│   ├── skills/                    # Domain workflow skills
│   ├── agents/                    # Specialized subagents
│   └── plans/                     # Implementation plans
├── common/
│   ├── pyproject.toml             # mfa-common — shared logging, utilities
│   └── src/mfa_common/
├── backend/
│   ├── Dockerfile                 # API + migration entrypoint
│   ├── docker/entrypoint.sh
│   └── src/mfa/                   # ingestion, scoring, rag, workers
├── crawler/
│   ├── Dockerfile                 # Playwright crawl worker
│   └── src/mfa_crawler/           # DOM parsers, crawl consumer
├── ml/
│   ├── Dockerfile                 # Score worker + training CLI
│   └── src/mfa_ml/                # rules, ensemble, calibration, SHAP
├── infra/
│   └── terraform/                 # AWS resources
└── frontend/
    └── src/                       # Review UI + Bot UI
```

## Local development (Docker)

Run the full local stack from the **repository root**:

```bash
cp .env.example .env
docker compose up -d          # postgres + backend-api
docker compose --profile workers up -d   # + crawler-worker, ml-worker
```

| Compose service   | Dockerfile            | Port / role                          |
| ----------------- | --------------------- | ------------------------------------ |
| `postgres`        | (official image)      | 5432 — signal store                  |
| `backend-api`     | `backend/Dockerfile`  | 8000 — FastAPI (ingestion, jobs, signals) |
| `crawler-worker`  | `crawler/Dockerfile`  | Postgres job poll → crawl → signal_snapshots |
| `ml-worker`       | `ml/Dockerfile`       | score consumer (stub)                |

Default app env: `ENV=local`. Docker Compose uses the **repo root** `.env`; native backend dev uses `backend/.env` (localhost vs `postgres` hostname). See root `README.md` § Environment files.

Native dev (without Docker): from **repo root**, `uv sync` then Postgres via Compose:

```bash
uv sync --all-packages          # install all workspace members
docker compose up -d postgres
cp backend/.env.example backend/.env
uv run --directory backend alembic upgrade head
uv run --directory backend uvicorn mfa.main:app --reload --port 8000
```



## Classification output contract

Every scoring result must include:

| Field           | Values / notes                                           |
| --------------- | -------------------------------------------------------- |
| `tier`          | `MFA_High` \| `MFA_Medium` \| `MFA_Low` \| `Non_MFA` \| `Uncertain` |
| `mfa_score`     | Calibrated 0–1                                           |
| `confidence`    | `high` \| `medium` \| `low`                              |
| `top_signals`   | Ranked feature contributions (SHAP or rules)             |
| `explanation`   | Template or LLM narrative citing only retrieved evidence |
| `evidence_hash` | Hash of signal snapshot for audit                        |

**Action mapping:** High → block; Medium → HITL; Low → monitor; Uncertain → HITL.

## Implementation naming

Use **production-oriented names** in code — milestone scope lives in `docs/ROADMAP.md`, not in identifiers.

| Use | Avoid |
|-----|-------|
| `SignalFeatures`, `SignalSnapshotPayload` | `POCFeatureSignals`, `Mvp*` prefixes |
| `schema_version: v1` | `poc-v1` in new writes |
| `CRAWL_FEATURE_NAMES`, `ENRICHMENT_FEATURE_NAMES` | `POC_FEATURE_NAMES` |
| `TODO(MVP):` / `TODO(Production):` comments | Phase names in class/module names |
| `ENV=local` | `ENV=poc` |

Canonical schema: `backend/src/mfa/schemas/signals.py` · `docs/SIGNALS.md`

## Agent workflow

1. **Read first:** `docs/ARCHITECTURE.md`, `docs/DOMAIN.md`, `docs/ROADMAP.md` — know current milestone scope
2. **ADRs:** `docs/ADRS.md` before changing model, vector store, or orchestration choices
3. **Signals:** `docs/SIGNALS.md` before adding/changing feature schema
4. **RAG:** `docs/RAG.md` before bot or retrieval changes
5. **Security:** `docs/GUARDRAILS.md` + `.cursor/rules/mfa-security.mdc` for all AI-facing code
6. **Cursor rules:** `.cursor/rules/mfa-*.mdc` — follow stack and layer conventions
7. **Skills:** `.cursor/skills/` — use domain workflows for classifier, crawler, RAG, ADRs
8. **Subagents:** `.cursor/agents/` — delegate architecture, ML, RAG, crawler, security, UI work
9. **Plans:** save implementation plans to `.cursor/plans/` or `docs/plans/YYYY-MM-DD-<feature>.md` — see [`docs/plans/2026-07-05-phased-build-plan.md`](docs/plans/2026-07-05-phased-build-plan.md) for phased task list



## Milestone scope (planning only)

Roadmap phases define **what to build when** — not how to name code. See `docs/plans/2026-07-05-phased-build-plan.md` for task IDs.

| Milestone      | Duration     | Key deliverables                                                                                   |
| -------------- | ------------ | -------------------------------------------------------------------------------------------------- |
| **Baseline**   | 6–8 weeks    | Single-persona crawl, rules + XGBoost, template explanations, Postgres, ingestion + signals API   |
| **MVP**        | +10–12 weeks | Dual-persona crawl, LLM explanations, RAG v1, review console, OpenSearch, Redis, audit v1           |
| **Production** | +12–16 weeks | Near-real-time path, pre-bid API, auto-retrain, RAG v2, SSO/RBAC, multi-region DR                |

**Do not implement Production-only features unless explicitly requested.** Check `docs/ROADMAP.md` before adding MVP/Production capabilities.

## Patterns

- **Retrieve-first RAG:** No generation without evidence pack; citation validator on every claim
- **LLM scope:** Explanation + RAG only — never primary MFA classifier (ADR-001)
- **Dual-persona crawl:** Direct + simulated Outbrain/Taboola referrer; 60s dwell — TODO(MVP) for referral persona
- **Versioned signals:** `signals_v{n}` per `url_id`; never overwrite without version bump
- **HITL:** Override stores `final_label` + `override_reason`; does not delete ML score
- **Async workers:** Crawl and LLM calls off the hot API path via SQS/ECS



## Security defaults

- LLM context = retrieved JSON evidence only; no open web browsing until MVP RAG ships
- Input sanitizer on RAG queries; tool calls whitelisted
- Tenant isolation; RBAC; PII scrubbing in logs
- Secrets in AWS Secrets Manager + KMS — never in code
- Immutable audit log for every score, explanation, and RAG answer



## Do not

- Use LLM-only classification (violates ADR-001)
- Score domain-only without page-section granularity
- Block on homepage crawl alone (easily gamed)
- Trust viewability or IVT flags as sole MFA signals
- Skip citation validation in RAG responses
- Commit `.env`, credentials, or production keys
- Add dependencies without justification in change summary



## Exploration

Prefer `Glob` / `Grep` / `Read` on this repo. Read `docs/` before implementing domain logic. Use `.cursor/agents/` subagents for specialized deep dives.