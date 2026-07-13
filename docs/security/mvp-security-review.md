# MVP Security Review Checklist (MVP-5.4)

**Reviewer:** `mfa-security-reviewer`  
**Scope:** RAG chat API, review overrides, auth stub, audit trail  
**Status:** Resolved for local pilot; AWS path in `docs/security/aws-deployment-checklist.md` (MVP-5.4)

## RAG / LLM

- [x] Chat input sanitized (`mfa.rag.sanitizer`)
- [x] Retrieve-first — no generation without evidence pack
- [x] Citation validator strips ungrounded citations
- [x] Audit event per `POST /api/v1/chat` with `evidence_hash` binding when available
- [x] No open web browsing in RAG context (ADR-005)

## Auth / RBAC

- [x] Cognito JWT validation (`Authorization: Bearer`) when `COGNITO_USER_POOL_ID` is set
- [x] `cognito:groups` mapped to MFA roles: admin, reviewer, ad_ops, auditor, read_only
- [x] Dev header fallback (`X-MFA-Role` / `X-MFA-Actor`) only when Cognito is not configured and auth is not strict
- [x] `GET /reviews/queue` and `GET /blocklist` require reviewer+ roles
- [x] `MFA_REQUIRE_AUTH=1` or `ENV=prod` requires Bearer token (or dev headers only when Cognito unset + not strict)
- [x] Terraform Cognito module: user pool, SPA client, RBAC groups (MVP-4.6)
- [ ] API Gateway authorizer in front of ECS (optional hardening — JWT validated in FastAPI today)

## Reviewer overrides

- [x] ML score preserved on `review_overrides` row
- [x] Mandatory `override_reason` enum
- [x] Audit event `review.override` on every override

## Data protection

- [x] No full URLs with PII query params in logs (structured logging)
- [x] Tenant isolation documented — single-tenant MVP
- [x] Secrets via env / Secrets Manager — no `.env` in repo

## Findings

| ID | Severity | Finding | Status |
|----|----------|---------|--------|
| SEC-001 | Medium | Header auth defaults to reviewer in local `ENV` | Mitigated — strict mode + Cognito for deployed MVP |
| SEC-002 | Low | OpenSearch stub returns empty (SQL-only RAG) | Resolved — `opensearch_client.py` + indexing worker (MVP-3.1/3.2); SQL fallback when endpoint unset |
| SEC-003 | Medium | SQS not wired to workers (Postgres poll) | Resolved — SQS consumers in crawl/ml workers with Postgres fallback (MVP-1.3) |

**Sign-off:**

```
Reviewer: mfa-security-reviewer (automated checklist)
Date: 2026-07-10
Approved for MVP pilot: [x] Yes  [ ] No
```
