# MFA Platform — Architecture Decision Records

## ADR-001: Hybrid Rules + ML + LLM

**Decision:** Rules catch known patterns; XGBoost/LightGBM for ranking; LLM only for explanation and RAG.

**Rationale:** Precision at scale, auditability, cost. LLM-only is slow, costly, hard to calibrate.

## ADR-002: Page-section granularity

**Decision:** Output tiered labels per URL path pattern, not binary domain flag.

**Rationale:** Homepage ≠ article experience; ANA/DV guidance emphasizes shades of gray.

## ADR-003: Dual-persona headless crawling

**Decision:** Playwright with (a) direct navigation and (b) simulated content-recommendation referrer; 60s dwell for refresh detection.

**Build vs buy:** Build crawler core; augment with commercial verification APIs for traffic signals.

## ADR-004: Vector store — OpenSearch k-NN

**Decision:** OpenSearch Serverless with hybrid BM25 + k-NN; metadata filters on `domain`, `url_id`, `signal_version`, `doc_type`.

**Alternatives:** Pinecone (POC), pgvector (simpler MVP), Azure AI Search, Vertex AI Vector Search.

## ADR-005: LLM selection

| Use case | Model tier |
|----------|------------|
| Explanation generation | Cost-effective (GPT-4o-mini / Claude Haiku) |
| RAG answers | Higher grounding (GPT-4o / Claude Sonnet) |
| Content quality rubric | Small classifier + occasional LLM |

**Guardrail:** LLM receives only retrieved JSON evidence; no open web in MVP.

## ADR-006: Event-driven microservices

**Decision:** API Gateway + Lambda/ECS scoring; SQS queues; Step Functions for batch.

## ADR-007: Feature store — Postgres + S3 (MVP)

**Decision:** Postgres JSONB for signals; S3 for artifacts. Feast/DynamoDB deferred until sub-100ms online serving needed.

## ADR-008: Integration strategy

Inbound: DSP export, REST API, webhook, optional OpenRTB sink.
Outbound: Blocklist API, pre-bid segment, BI dashboards, Slack alerts.
Buy: Traffic enrichment as one signal, not source of truth.

## ADR-009: Cloud primary — AWS

AWS for Kinesis/Glue, OpenSearch, Step Functions. Azure/GCP equivalents in plan Section 8.
