---
name: Multi-Agent Execution Plan
overview: Orchestration guide for completing POC-5 exit, MVP, and Production phases using Cursor agents, subagents, and layer-specific skills.
current_phase: POC-5
next_phase: MVP-1
created: 2026-07-10
---

# MFA Platform — Multi-Agent Execution Plan

**Purpose:** Route work across specialized agents and parallel subagents while preserving scope gates, ADRs, and audit requirements.

**Authoritative task IDs:** [`docs/plans/2026-07-05-phased-build-plan.md`](../../docs/plans/2026-07-05-phased-build-plan.md)  
**Full HLD:** [`.cursor/plans/mfa_platform_architecture_48645023.plan.md`](mfa_platform_architecture_48645023.plan.md)

---

## Phase status (2026-07-10)

| Phase | Status | Gate |
|-------|--------|------|
| P0 Foundation | ✅ Complete | Monorepo, compose, schema, ingestion |
| POC-1 Data & schema | ✅ Complete | `SignalFeatures`, gold labels |
| POC-2 Crawler | ✅ Complete | Single-persona, 100-domain spike |
| POC-3 ML scoring | ✅ Complete (metrics gap documented) | `ml/artifacts/v1/metrics.json` — precision/recall below target |
| POC-4 Workers | ✅ Complete | crawl→score async, audit, classifications API |
| **POC-5 Exit** | **✅ Complete** | Batch eval done; gaps documented → MVP remediation |
| MVP-1 → MVP-5 | **Next** | Dual-persona, S3, RAG, review UI |
| PROD-1 → PROD-5 | ⏳ Blocked on MVP exit | NRT, pre-bid, SSO, DR |

**Active sprint plan:** [`docs/plans/2026-07-10-poc-5-exit.md`](../../docs/plans/2026-07-10-poc-5-exit.md)

---

## Agent roster

| Agent | File | Primary phases | Delegates to |
|-------|------|----------------|--------------|
| **Platform orchestrator** | `.cursor/agents/mfa-platform-orchestrator.md` | All | Layer agents below |
| **Architect** | `.cursor/agents/mfa-architect.md` | Scope, ADRs, phase gates | — |
| **Backend engineer** | `.cursor/agents/mfa-backend-engineer.md` | POC-5, MVP-2, MVP-4 | `mfa-api` rule |
| **Crawler engineer** | `.cursor/agents/mfa-crawler-engineer.md` | POC-2, MVP-1 | `mfa-crawler` skill |
| **ML engineer** | `.cursor/agents/mfa-ml-engineer.md` | POC-3, POC-5, MVP-2, PROD-2 | `mfa-classifier` skill |
| **RAG engineer** | `.cursor/agents/mfa-rag-engineer.md` | MVP-3, PROD-3 | `mfa-rag-bot` skill |
| **Review UI engineer** | `.cursor/agents/mfa-review-ui-engineer.md` | MVP-4 | `mfa-review-ui` rule |
| **Infra engineer** | `.cursor/agents/mfa-infra-engineer.md` | MVP-1, MVP-4, PROD-1, PROD-4 | `mfa-infra-aws` rule |
| **Security reviewer** | `.cursor/agents/mfa-security-reviewer.md` | MVP-3+, all AI-facing merges | `mfa-security` rule |

---

## Orchestration patterns

### Pattern 1 — Phase kickoff (orchestrator)

```
User: "Start MVP-1"
  → mfa-platform-orchestrator reads phase plan + exit checklist
  → mfa-architect confirms scope gate passed
  → Spawn parallel subagents:
      - mfa-infra-engineer (MVP-1.1 Terraform)
      - mfa-crawler-engineer (MVP-1.4 dual-persona spike)
  → Orchestrator merges PRs, updates phased build plan status
```

### Pattern 2 — Layer sprint (single phase, parallel tracks)

Use when tasks have **no shared-file conflicts**:

| Track | Agent | Example tasks |
|-------|-------|---------------|
| A | `mfa-infra-engineer` | MVP-1.1, MVP-1.2, MVP-1.3 |
| B | `mfa-crawler-engineer` | MVP-1.4, MVP-1.5 |
| C | `mfa-backend-engineer` | MVP-1.6 Redis cache |
| D | `mfa-ml-engineer` | MVP-2.1 feature expansion |

**Rule:** One branch per track: `cursor/mvp-1-infra`, `cursor/mvp-1-crawl`, etc.

### Pattern 3 — Vertical slice (E2E feature)

Use for user-visible flows (review override, RAG chat):

```
mfa-backend-engineer (API) → mfa-review-ui-engineer (UI) → mfa-security-reviewer (gate)
```

Sequential handoffs with shared contract (OpenAPI / Pydantic models) defined first.

### Pattern 4 — Exit gate review

Before advancing phase:

1. `mfa-architect` — checklist vs `docs/ROADMAP.md`
2. `mfa-ml-engineer` — metrics report (POC/MVP)
3. `mfa-security-reviewer` — AI-facing + audit (MVP+)
4. Orchestrator updates `docs/plans/2026-07-05-phased-build-plan.md` exit checkboxes

---

## Subagent dispatch guide

| Situation | Subagent type | Notes |
|-----------|---------------|-------|
| Broad codebase search | `explore` (medium) | Read-only; report paths + patterns |
| Single-file API change | `generalPurpose` or layer agent | Keep scope to one task ID |
| Terraform / AWS | `mfa-infra-engineer` | Never mix with crawler in same PR |
| Parallel independent tasks | Multiple `Task` agents in **one message** | e.g. MVP-1.4 + MVP-1.1 |
| Pre-merge AI/RAG | `mfa-security-reviewer` | Required for MVP-3.6+ |
| Architecture decision | `mfa-architect` | ADR required for model/vector/orchestration changes |

**Branch safety:** All agents work on `cursor/<phase>-<task-id>-<summary>` branches. PR into `develop` only.

---

## Remaining phase plans

| Document | Phase | Duration |
|----------|-------|----------|
| [`docs/plans/2026-07-10-poc-5-exit.md`](../../docs/plans/2026-07-10-poc-5-exit.md) | POC-5 exit | ~1–2 weeks |
| [`docs/plans/2026-08-mvp-execution.md`](../../docs/plans/2026-08-mvp-execution.md) | MVP-1 → MVP-5 | 10–12 weeks |
| [`docs/plans/2026-11-production-execution.md`](../../docs/plans/2026-11-production-execution.md) | PROD-1 → PROD-5 | 12–16 weeks |

---

## Verification commands (all agents)

```bash
# Unit (always)
uv run --package mfa-backend pytest backend/tests/ -q
uv run --package mfa-ml pytest ml/tests/ -q
uv run --package mfa-crawler pytest crawler/tests/ -q -m "not integration"

# Integration (Postgres on :5432)
MFA_RUN_INTEGRATION=1 uv run --package mfa-backend pytest backend/tests/ -q
```

---

## Scope gates (do not skip)

| From → To | Required |
|-----------|----------|
| POC → MVP | POC exit checklist in phased build plan |
| MVP → Production | MVP exit checklist + MVP-5.4 security review |
| Baseline code in Production | Explicit user request only |

---

## Immediate next actions (POC-5)

| Task ID | Status |
|---------|--------|
| POC-5.1 | ✅ Done |
| POC-5.2 | ✅ Done |
| POC-5.3 | ⏳ Track B — batch eval |
| POC-5.4 | ⏳ Track B — live metrics |
| POC-5.5 | ✅ Done |

**Metrics note:** Holdout eval (`ml/artifacts/v1/metrics.json`) shows precision/recall below POC targets due to sparse crawl features. POC-5.4 must document gap + remediation path (MVP-2.1 feature expansion) — do not block pipeline exit on metrics alone if ≥90% crawl success is met.
