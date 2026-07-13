---
inclusion: always
---

# MFA Platform — Core rules

Gate feature scope via `docs/ROADMAP.md` and `docs/plans/2026-07-05-phased-build-plan.md`.

## Naming (required)

- Production-oriented names: `SignalFeatures`, `SignalSnapshotPayload`, `schema_version: v1`
- No `POC`, `Mvp`, `poc-` prefixes in classes, modules, or constants
- Deferred work: `TODO(MVP):` / `TODO(Production):` comments pointing to `docs/ROADMAP.md`
- Local env: `ENV=local` · Canonical schema: `backend/src/mfa/schemas/signals.py`

## Architecture

`rules → ML ensemble → calibrator → explanation`. LLM for explanation + RAG only (ADR-001). Score at **URL/page-section** granularity with versioned evidence snapshots.

## Stack

Python 3.12+ · FastAPI · Playwright · XGBoost/LightGBM · Postgres JSONB · OpenSearch · Redis · S3 · AWS · React+TS · **uv** workspace (`pyproject.toml`) · Docker Compose (repo root)

## Classification output (required)

Every score must emit: `tier`, `mfa_score`, `confidence`, `top_signals`, `explanation`, `evidence_hash`.
Tiers: `MFA_High` | `MFA_Medium` | `MFA_Low` | `Non_MFA` | `Uncertain`

## Do not

- LLM-only classification · domain-only scoring · homepage-only crawl
- Trust viewability or IVT as sole MFA signals
- Skip audit trail on scores, overrides, or RAG answers
