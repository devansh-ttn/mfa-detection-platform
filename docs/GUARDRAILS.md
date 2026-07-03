# MFA Platform — Risk & Guardrails

| Risk | Control |
|------|---------|
| Hallucination | Retrieval-only context; citation validator; structured output schema |
| Prompt injection | Input sanitizer; system prompt isolation; whitelisted tool calls; never follow instructions in crawled page text stored as data |
| False positives | Tiered output; HITL for Medium/Uncertain; page-level scoring; spend-weighted escalation |
| False negatives | Re-crawl schedule; reviewer feedback loop; drift alerts on feature distributions |
| Data leakage | Tenant isolation; RBAC; PII scrubbing; no cross-advertiser sharing without consent |
| Reviewer override | Mandatory reason code; dual-control for bulk block; `final_label` + `override_reason` stored alongside ML score |
| Auditability | Immutable audit log; `evidence_hash` on every score/explanation/RAG answer; configurable retention |
| Cost runaway | Crawl budget per domain; LLM token caps; 24h explanation cache; batch off-peak |
| Crawler abuse | Robots.txt respect (configurable); rate limits; user-agent identification |

## Reviewer reason codes (define during MVP)

Use structured enums, not free-text-only. Examples: `false_positive_publisher`, `referral_delta_expected`, `policy_exception`, `insufficient_evidence`, `vendor_disagreement`.

## Audit event minimum fields

`event_id`, `entity_type`, `entity_id`, `action`, `actor_id`, `occurred_at`, `evidence_hash`, `payload` (JSONB)
