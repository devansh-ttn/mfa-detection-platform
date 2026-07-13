# MVP Exit — Parallel Tracks (post UI)

**Created:** 2026-07-11  
**Parent:** [`2026-08-mvp-execution.md`](2026-08-mvp-execution.md)  
**Prerequisite:** MVP-4 UI polish + Cognito auth (MVP-4.6)

Run these tracks in parallel after the review console is functional.

---

## Track A — OpenSearch indexing (MVP-3.1 / MVP-3.2)

| Item | Path | Status |
|------|------|--------|
| Terraform Serverless collection | `infra/terraform/modules/opensearch/` | Done |
| Index mapping | `backend/src/mfa/rag/opensearch_mappings.py` | Done |
| BM25 client | `backend/src/mfa/rag/opensearch_client.py` | Done |
| Indexing worker | `backend/src/mfa/rag/indexer.py`, `worker.py` | Done |
| Hybrid retriever | `backend/src/mfa/rag/retriever.py` | Done |
| Compose profile | `docker compose --profile opensearch up indexer-worker` | Done |

**Verify:**

```bash
# With OPENSEARCH_ENDPOINT set
uv run --package mfa-backend python -m mfa.rag.worker
uv run --package mfa-backend pytest backend/tests/test_opensearch_indexer.py -q
```

**Branch:** `cursor/mvp-3-opensearch-indexing`

---

## Track B — SQS migration (MVP-1.3)

| Item | Path | Status |
|------|------|--------|
| SQS transport | `backend/src/mfa/ingestion/sqs_transport.py` | Done |
| Publish on ingest / score enqueue | `queue.py`, `score_poll.py` | Done |
| Crawl consumer (SQS + Postgres) | `crawler/src/mfa_crawler/consumer.py` | Done |
| ML consumer (SQS + Postgres) | `ml/src/mfa_ml/consumer.py` | Done |
| LocalStack init | `scripts/dev/init-localstack-sqs.sh` | Done |

**Verify:**

```bash
docker compose --profile localstack up -d
./scripts/dev/init-localstack-sqs.sh
# Add printed SQS_* vars to .env, restart workers
uv run --package mfa-backend pytest backend/tests/test_sqs_transport.py -q
```

**Branch:** `cursor/mvp-1-sqs-migration`

---

## Track C — Shadow mode 4-week run (MVP-5.1)

| Week | Action |
|------|--------|
| 1 | Ingest DSP inventory; daily `daily_blocklist_export.sh` |
| 2–3 | Reviewer overrides; `shadow_metrics.py` weekly |
| 4 | Go/no-go gates in `docs/runbooks/shadow-mode.md` |

Set `MFA_SHADOW_MODE=1` until Ad Ops sign-off. Blocklist API returns `shadow_mode: true`.

**Branch:** ops runbook only — no code merge gate

---

## Track D — AWS security review (MVP-5.4)

| Item | Path |
|------|------|
| Local MVP checklist | `docs/security/mvp-security-review.md` |
| AWS deployment checklist | `docs/security/aws-deployment-checklist.md` |

Run `mfa-security-reviewer` before terraform apply to `prod` and before DSP block enforcement.

**Branch:** `cursor/mvp-5-security-aws`

---

## MVP exit checklist (update on completion)

- [x] SQS consumers wired with Postgres fallback
- [x] OpenSearch indexing worker + hybrid retriever
- [ ] Shadow mode 4-week run completed (human / Ad Ops)
- [ ] MVP-5.4 AWS checklist signed off
- [ ] Dual-persona + refresh in production crawl path
- [ ] RAG citation validator on test query set
- [ ] Reviewer console E2E with Cognito
