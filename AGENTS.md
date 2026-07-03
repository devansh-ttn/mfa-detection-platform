# AGENTS.md — MFA Detection Platform

Context for humans and coding agents (including Cursor) working on the **Made-For-Advertising (MFA) detection platform**.

## Mission

Build a **multi-signal, hybrid ML + LLM system** that ingests ad-inventory URLs, extracts page-level evidence via headless crawling, scores MFA risk with calibrated confidence, explains decisions with cited signals, routes uncertain cases to human reviewers, and exposes a **RAG bot** grounded in structured signals and policy corpora.

**Core principle:** Score at **URL/page-section granularity** (not domain-only). Store **versioned evidence snapshots** for audit and RAG grounding. Combine crawl + traffic + programmatic metadata — no single signal is sufficient.

## Stack (planned)

| Layer | Technology |
|-------|------------|
| API | FastAPI (async), API Gateway, OpenAPI |
| Crawler | Playwright cluster (dual-persona: direct + referral referrer) |
| ML | Rules engine + XGBoost/LightGBM ensemble + confidence calibrator |
| LLM | Bedrock (Claude) or Azure OpenAI — explanations + RAG only, not primary classifier |
| Signal store | PostgreSQL 16 (JSONB feature vectors) |
| Vector / search | OpenSearch Serverless (hybrid BM25 + k-NN) |
| Cache | Redis (hot domain tier + explanation cache) |
| Artifacts | S3 (screenshots, HTML, parquet) |
| Orchestration | SQS priority queues, Step Functions (batch), ECS Fargate (crawler workers) |
| Audit | DynamoDB + S3 Object Lock (immutable trail) |
| Web | Vite + React + TypeScript (reviewer console + bot UI) |
| Dashboards | QuickSight (ops metrics) |
| Cloud | **AWS primary** (Azure/GCP equivalents documented) |
| Tooling | **uv** (`backend/`), **npm** (`frontend/`) |

## Repository layout (target)

```
ai-champions-assessment-cursor/
├── AGENTS.md                      # This file — agent entry point
├── README.md
├── docs/
│   ├── ARCHITECTURE.md            # System components & data flow
│   ├── DOMAIN.md                  # MFA terminology & tier taxonomy
│   ├── ADRS.md                    # Architecture decision records
│   ├── SIGNALS.md                 # Feature schema (~40–60 features)
│   ├── RAG.md                     # RAG bot design & response contract
│   ├── ROADMAP.md                 # POC → MVP → Production phases
│   └── GUARDRAILS.md              # Risk controls & compliance defaults
├── .cursor/
│   ├── rules/                     # mfa-*.mdc project rules
│   ├── skills/                    # Domain workflow skills
│   ├── agents/                    # Specialized subagents
│   └── plans/                     # Implementation plans
├── backend/
│   └── src/mfa/                   # ingestion, scoring, rag, workers
├── crawler/
│   └── src/                       # Playwright workers, DOM parsers
├── ml/
│   └── src/                       # training, calibration, SHAP
├── infra/
│   └── terraform/                 # AWS resources
└── frontend/
    └── src/                       # Review UI + Bot UI
```

## Classification output contract

Every scoring result must include:

| Field | Values / notes |
|-------|----------------|
| `tier` | `MFA_High` \| `MFA_Medium` \| `MFA_Low` \| `Non_MFA` \| `Uncertain` |
| `mfa_score` | Calibrated 0–1 |
| `confidence` | `high` \| `medium` \| `low` |
| `top_signals` | Ranked feature contributions (SHAP or rules) |
| `explanation` | Template or LLM narrative citing only retrieved evidence |
| `evidence_hash` | Hash of signal snapshot for audit |

**Action mapping:** High → block; Medium → HITL; Low → monitor; Uncertain → HITL.

## Agent workflow

1. **Read first:** `docs/ARCHITECTURE.md`, `docs/DOMAIN.md`, `docs/ROADMAP.md` — know current phase scope
2. **ADRs:** `docs/ADRS.md` before changing model, vector store, or orchestration choices
3. **Signals:** `docs/SIGNALS.md` before adding/changing feature schema
4. **RAG:** `docs/RAG.md` before bot or retrieval changes
5. **Security:** `docs/GUARDRAILS.md` + `.cursor/rules/mfa-security.mdc` for all AI-facing code
6. **Cursor rules:** `.cursor/rules/mfa-*.mdc` — follow stack and layer conventions
7. **Skills:** `.cursor/skills/` — use domain workflows for classifier, crawler, RAG, ADRs
8. **Subagents:** `.cursor/agents/` — delegate architecture, ML, RAG, crawler, security, UI work
9. **Plans:** save implementation plans to `.cursor/plans/` or `docs/plans/YYYY-MM-DD-<feature>.md`

## Phase scope

| Phase | Duration | Key deliverables |
|-------|----------|------------------|
| **POC** | 6–8 weeks | 5K–10K URLs, single-persona crawl, rules + XGBoost, template explanations, Postgres only |
| **MVP** | +10–12 weeks | Dual-persona crawl, tiered scoring, LLM explanations, RAG v1, review console, OpenSearch, audit v1 |
| **Production** | +12–16 weeks | Near-real-time path, pre-bid API, auto-retrain, RAG v2, SSO/RBAC, multi-region DR |

**Do not implement Production-only features during POC unless explicitly requested.**

## Patterns

- **Retrieve-first RAG:** No generation without evidence pack; citation validator on every claim
- **LLM scope:** Explanation + RAG only — never primary MFA classifier (ADR-001)
- **Dual-persona crawl:** Direct navigation + simulated Outbrain/Taboola referrer; 60s dwell for refresh
- **Versioned signals:** `signals_v{n}` per `url_id`; never overwrite without version bump
- **HITL:** Override stores `final_label` + `override_reason`; does not delete ML score
- **Async workers:** Crawl and LLM calls off the hot API path via SQS/ECS

## Security defaults

- LLM context = retrieved JSON evidence only; no open web browsing in MVP
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
