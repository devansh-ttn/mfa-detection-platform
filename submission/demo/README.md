# MFA Detection Platform — End-to-End Demo

A self-contained demonstration of the full MFA detection pipeline. No server,
no database, no ML model files required — runs with the Python standard library.

## Quick start

```bash
python submission/demo/end_to_end_demo.py
```

Or from the project root:

```bash
cd /Users/devanshkumar/Workspaces/ttn/mfa-detection-platform
python submission/demo/end_to_end_demo.py
```

Requires: **Python 3.9+** (no pip install needed — stdlib only).

---

## What it demonstrates

The script runs 5 pipeline stages against two test URLs:

| Stage | What runs | Real code equivalent |
|-------|-----------|----------------------|
| 1. URL Ingestion | URL normalisation + deterministic `url_id` via UUID5 | `POST /api/v1/urls` ingestion handler |
| 2. Signal Extraction | Mock `SignalFeatures` v1.1 (16 crawl features) + `compute_evidence_hash()` | `crawler/` Playwright worker + `schemas/signals.py` |
| 3. Classification | Rules engine → mock XGBoost → calibrator → tier mapping → explanation | `ml/src/mfa_ml/scoring/pipeline.py:classify_snapshot()` |
| 4. RAG Query | Sanitise → intent classify → retrieve evidence → ground response → validate citations | `backend/src/mfa/rag/service.py:answer_query()` |
| 5. Review Override | Reviewer disagrees → `final_label` stored alongside ML score → audit event | `POST /api/v1/reviews` + `audit/writer.py` |

---

## Test URLs

- **URL A** — `clickbait-news-farm.example.com` — textbook MFA site:
  - `ad_to_content_ratio = 0.78`, `refresh_events_60s = 7`, `content_word_count = 180`
  - Expected: `MFA_High`, rules engine fires, `recommended_action = block`

- **URL B** — `quality-journalism.example.com` — legitimate publisher:
  - `ad_to_content_ratio = 0.18`, `refresh_events_60s = 0`, `content_word_count = 1450`
  - Expected: `Non_MFA` or `MFA_Low`, XGBoost path, `recommended_action = allow`

---

## Codebase mapping

| Demo component | Real file |
|----------------|-----------|
| `SignalFeatures` dataclass | `backend/src/mfa/schemas/signals.py` |
| `compute_evidence_hash()` | `backend/src/mfa/schemas/signals.py` |
| `ClassificationOutput` dataclass | `ml/src/mfa_ml/scoring/output.py` |
| `classify_snapshot()` | `ml/src/mfa_ml/scoring/pipeline.py` |
| Rules engine | `ml/src/mfa_ml/rules/engine.py` |
| `render_explanation()` | `ml/src/mfa_ml/scoring/explanation.py` (Jinja2 templates) |
| `RAGResponse`, `Citation` dataclasses | `backend/src/mfa/rag/schemas.py` |
| `sanitize_query()`, `classify_intent()` | `backend/src/mfa/rag/sanitizer.py` |
| `retrieve_evidence()` | `backend/src/mfa/rag/retriever.py` |
| `build_grounded_response()`, `validate_citations()` | `backend/src/mfa/rag/validator.py` |
| `answer_query()` | `backend/src/mfa/rag/service.py` |
| `write_audit_event()` | `backend/src/mfa/audit/writer.py` |

---

## Architecture notes

### Evidence hash
Every stage in the pipeline binds to the same `evidence_hash` — a SHA-256 of the
canonical (sorted-key) JSON of the signal snapshot. This ensures:
- Classification, RAG response, and audit events are all traceable to the same crawl evidence
- Cache keys for RAG responses (24h TTL) are deterministic
- Audit records cannot be silently tampered with

### Retrieve-first RAG (ADR-001 guardrail)
The RAG bot never generates an answer without first retrieving an evidence pack.
All citations in the response must map to a `chunk_id` from the retrieved pack.
If citation validation fails, the response is rejected and escalated.

### ML score preservation
A reviewer override stores `final_label + override_reason` as a new record.
The original ML `mfa_score` is never overwritten — both are available for model
retraining and audit review.

---

## Dependencies

None beyond Python 3.9+ stdlib:
- `hashlib`, `json`, `uuid`, `datetime`, `dataclasses`, `typing`, `math`, `pprint`
