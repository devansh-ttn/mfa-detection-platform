# MFA Detection Platform — Lead/Architect Assessment Slide Deck

---

## Slide 1: Title

# MFA Detection Platform
### AI-Enabled Made-For-Advertising Classification, Explanation & RAG Bot

**Role:** Lead / Solution Architect
**Date:** July 2026
**Status:** Baseline/POC Complete → MVP In Progress

> **Note:** This deck accompanies the full submission report (`report.html`) and the
> end-to-end demo (`demo/end_to_end_demo.py`). All code references are live in the repository.

---

## Slide 2: Problem Statement & Objectives

**Made-For-Advertising (MFA) sites cost advertisers billions in wasted spend annually**

- MFA sites are engineered to pass surface checks: clean homepage, thin article pages
- Direct vs referral navigation shows completely different ad behaviour (evasion tactic)
- Existing binary domain flags miss the gradient — homepage ≠ article experience
- Viewability and IVT flags alone do not catch MFA (MFA traffic is often human and valid)

**Platform objectives:**
- Score at URL / page-section granularity — not domain-only
- Calibrated confidence with 5-tier output: `MFA_High → Non_MFA → Uncertain`
- Explain every decision with cited signal evidence
- Route uncertain/high-spend cases to human reviewers (HITL)
- Expose a RAG bot grounded in signals + policy corpora

> **Note:** Key business metric — Precision ≥ 85%, Recall ≥ 70% on gold-label set (615 URLs).

---

## Slide 3: Assumptions

- Platform targets **Ad Ops, Campaign Managers, and Reviewers** — not data scientists
- **AWS is primary cloud**; Azure/GCP equivalents are documented in the roadmap
- Baseline/POC is **complete** as of 2026-07-10; this submission covers MVP → Production
- "Working code" is production-oriented (FastAPI + XGBoost + RAG service), not a prototype
- **LLM provider:** AWS Bedrock (Claude Sonnet/Haiku) in MVP; GPT-4o via Azure OpenAI private link as alternative
- Crawl targets are third-party URLs; legal/robots.txt compliance handled per jurisdiction
- Gold-label dataset: 615 URLs from internal Ad Ops review; vendor lists used only for bootstrap
- **Traffic enrichment** (paid_traffic_pct etc.) requires a third-party API — treated as one signal, not sole truth
- Precision ≥ 85%, Recall ≥ 70% is the Baseline target; MVP expands feature set (16 → 60 features)

> **Note:** Viewability and IVT scores are explicitly excluded as primary MFA signals — MFA traffic is often valid human traffic.

---

## Slide 4: System Architecture — Layer Overview

**8-layer architecture from ingestion to observability**

| Layer | Key Components |
|-------|---------------|
| **Ingestion** | REST API (FastAPI), Step Functions batch, URL dedup/normaliser |
| **Signal Extraction** | Playwright dual-persona crawler, DOM parser, domain enricher |
| **Data Stores** | Postgres JSONB, S3 artifacts, OpenSearch vectors, Redis cache, DynamoDB audit |
| **AI / ML** | Rules Engine → XGBoost Ensemble → Calibrator → HITL Router |
| **Explanation** | Jinja2 templates (Baseline) → LLM with Bedrock (MVP) |
| **RAG Bot** | Chat Gateway → Sanitiser → Intent → Hybrid Retriever → Citation Validator |
| **Review UI** | React+TS Reviewer Console, QuickSight dashboard, Bot Chat UI |
| **Observability** | CloudWatch, X-Ray, SLO dashboards, drift alerts |

**Design principles:**
- Async first — crawl and LLM calls never block the hot API path
- Evidence versioning — every signal snapshot is immutable with SHA-256 binding
- Retrieve-first RAG — no LLM generation without an evidence pack (ADR-001)

> **Note:** Full architecture diagram with ASCII flow is in report Section 1.

---

## Slide 5: End-to-End Data Flow

```
DSP/SSP Inventory Exports
         │
         ▼
  INGESTION  ──►  URL Dedup  ──►  url_id  ──►  SQS Priority Queue
         │
         ▼
  SIGNAL EXTRACTION (Playwright)
  ├─ Persona A: direct navigation
  └─ Persona B: Outbrain/Taboola referrer simulation (60s dwell)
         │
         ▼
  DATA STORES
  Postgres JSONB ── signal_snapshots (versioned)
  S3             ── HTML + screenshots + parquet
  Redis          ── domain tier cache (24h TTL)
         │
         ▼
  AI / ML LAYER
  Rules Engine → XGBoost → Calibrator → Tier Mapping
  ├─ confidence OK    →  Explanation  →  Export / Dashboard
  └─ low conf / high spend  →  HITL Review Queue
         │
         ▼
  AUDIT LOG (IMMUTABLE)
  Every event bound by evidence_hash (SHA-256)
```

**RAG Bot (parallel path):** Query → Sanitiser → Intent → SQL+Vector Retrieval → Grounded LLM → Citation Validator → RAGResponse

> **Note:** The dual-persona crawl is the key MFA-evasion countermeasure — referral vs direct behaviour delta is a top-tier signal.

---

## Slide 6: Classification Pipeline Deep Dive

**Pipeline: Rules → XGBoost → Calibrator → Tier → SHAP → Explanation**

```
SignalFeatures (v1.1)  ──►  Rules Engine
                              │
               rule fires ◄──┤ (high-precision deterministic)
               (classifier="rules")
                              │ no match
                              ▼
                         XGBoost Ensemble
                              │
                              ▼
                       Confidence Calibrator
                       (Isotonic/Platt scaling)
                              │
                              ▼
                         Tier Mapping
                    ┌─────────────────────┐
                    │  ≥0.80 → MFA_High   │
                    │  ≥0.60 → MFA_Medium │
                    │  ≥0.40 → MFA_Low    │
                    │  <0.40 → Non_MFA    │
                    │  low conf → Uncertain│
                    └─────────────────────┘
                              │
               ┌──────────────┴──────────────┐
               ▼                             ▼
          SHAP Top-5 Signals            HITL Router
          Jinja2 Explanation         (Medium/Uncertain/
          + evidence_hash            high-spend URLs)
```

**Output contract:** `tier | mfa_score | confidence | top_signals[≤5] | explanation | evidence_hash | classifier | schema_version`

> **Note:** LLM is never in the classification path (ADR-001). It is only used for explanation rendering in MVP and for RAG answers.

---

## Slide 7: Data Signals — Tier 1 (Highest Value)

**Top-tier signals combine for precision — no single signal is sufficient**

| Signal Category | Key Features | Why It Matters | Gaming Risk |
|-----------------|--------------|----------------|-------------|
| **Ad Density** | `ad_to_content_ratio`, `ads_above_fold`, `ad_slots_count`, `sticky_ad_count` | ANA/IAB core MFA criterion; measures arbitrage intent | Low — hard to fake across article paths |
| **Ad Refresh** | `refresh_events_60s`, `avg_refresh_interval_sec` | MFA monetises via impression recycling | Medium — can be rate-limited for crawlers |
| **Traffic Source Skew** | `paid_traffic_pct`, `social_traffic_pct`, `organic_traffic_pct` | Real publishers diversify; MFA depends on bought traffic | Medium — Similarweb-style data can lag |
| **Referral vs Direct Delta** | `referral_direct_delta_score` | Classic MFA evasion: clean homepage, ad-farm article pages | Low — requires dual-persona crawl to detect |
| **Content Quality** | `content_word_count`, `content_uniqueness_score`, `author_page_exists`, `llm_content_quality_score` | Editorial legitimacy proxy | Medium — AI-generated content can score high |

**Signals to avoid as sole MFA indicators:**
- Viewability alone (MFA often scores _high_ viewability)
- IVT/fraud flags alone (MFA traffic is often human and valid)
- Homepage-only crawl (easily gamed)
- Single-domain block (ignore subdomains)

---

## Slide 8: Data Signals — Schema and Enrichment

**v1.1 implemented (16 features) → MVP target ~60 features**

Current crawl features (all in `SignalFeatures` Pydantic model):
- `ad_to_content_ratio` · `ads_above_fold` · `ad_slots_count` · `sticky_ad_count`
- `content_word_count` · `refresh_events_60s` · `avg_refresh_interval_sec`
- `content_uniqueness_score` · `author_page_exists` · `slideshow_pagination_depth`
- `video_autoplay_count` · `page_load_ad_latency_ms` · `iframe_ad_count`
- `native_ad_count` · `outbound_link_count` · `image_to_text_ratio`

**MVP enrichment features (planned):**
- `domain_age_days` · `paid_traffic_pct` · `social_traffic_pct` · `organic_traffic_pct`
- `referral_direct_delta_score` · `sellers_json_risk_tier` · `historical_spend_usd`
- `campaign_ctr_vs_benchmark` · `simhash_dup_rate` · `llm_content_quality_score`

**Storage:** Postgres JSONB (online) + S3 Parquet (offline training)
**Null convention:** `null` = signal not applicable or not measured; `0` = measured zero

> **Note:** `evidence_hash = SHA-256(canonical_json(signals))` — binds every audit event to the exact feature vector.

---

## Slide 9: Architecture Decision Records (ADR-001 to ADR-004)

**ADR-001: Hybrid Rules + ML + LLM (not LLM-only)**
- **Decision:** Rules catch known patterns; XGBoost for ranking; LLM only for explanation and RAG
- **Rationale:** Precision at scale, auditability, cost — LLM-only is slow, costly, hard to calibrate
- **Trade-off:** More feature engineering upfront; lower hallucination risk in classification

**ADR-002: Page-section granularity with 5-tier output**
- **Decision:** Score per URL path pattern — `MFA_High | MFA_Medium | MFA_Low | Non_MFA | Uncertain`
- **Rationale:** ANA/DV guidance emphasises shades of gray; homepage ≠ article experience
- **Action mapping:** High → block; Medium/Uncertain → HITL; Low → monitor

**ADR-003: Dual-persona headless crawling (Build, not Buy)**
- **Decision:** Playwright with (a) direct navigation and (b) simulated Outbrain/Taboola referrer; 60s dwell
- **Build vs buy:** Build crawler core; augment with commercial APIs for traffic signals not observable via crawl
- **Rationale:** Referral/direct delta is a top MFA tell per IAB/IAS

**ADR-004: OpenSearch Serverless for vector store**
- **Decision:** Hybrid BM25 + k-NN; metadata filters on `domain`, `url_id`, `signal_version`, `doc_type`
- **Alternatives considered:** Pinecone (fast POC), pgvector (simpler MVP), Azure AI Search, Vertex AI Vector Search
- **Rationale:** Hybrid retrieval needed — exact domain lookups AND semantic similarity

---

## Slide 10: Architecture Decision Records (ADR-005 to ADR-009)

**ADR-005: LLM selection — tiered by use case**
- Explanation generation: Claude Haiku / GPT-4o-mini (cost-effective, structured JSON)
- RAG answers: Claude Sonnet / GPT-4o (better grounding adherence)
- Guardrail: LLM receives retrieved JSON evidence only — no open web in MVP

**ADR-006: Event-driven microservices (SQS + ECS + Step Functions)**
- API Gateway + ECS/Lambda for scoring; SQS priority queues; Step Functions for batch
- Decouples crawl latency from API; independent scaling of crawl vs scoring workers

**ADR-007: Postgres + S3 as feature store (Feast deferred)**
- MVP: Postgres JSONB signals; S3 artifacts — simpler, sufficient for pilot scale
- Production: Add Feast / DynamoDB for online serving if sub-100ms bid lookup required

**ADR-008: Integration strategy (inbound / outbound / buy)**
- Inbound: DSP CSV/S3, REST API, webhook, optional OpenRTB Kinesis sink
- Outbound: Blocklist API, pre-bid segment, BI (QuickSight/Looker), Slack alerts
- Buy: Traffic enrichment (Similarweb-style) as one signal — not source of truth

**ADR-009: AWS as primary cloud**
- Kinesis/Glue, OpenSearch, Step Functions batch orchestration, Bedrock LLM
- Azure/GCP equivalents fully documented — cloud-agnostic data contracts

---

## Slide 11: RAG Bot Architecture

**Retrieve-first, citation-validated, grounded responses**

```
User Query
    │
    ▼
Input Sanitiser          ← blocks prompt injection, strips PII
    │
    ▼
Intent Classifier        ← why_mfa | signal_attribution | change_detection | counter_evidence
    │
    ├─── SQL Path         ← "Why is X MFA?" → Postgres: classification + top_signals + explanation
    │
    └─── Vector Path      ← "Similar sites" → OpenSearch k-NN (RAG v2 / Production)
              │
              ▼
    Evidence Packager     ← assemble chunks with doc_type + metadata filters
              │
              ▼
    Grounded LLM          ← context = evidence pack ONLY (ADR-001 guardrail)
    (Bedrock Claude Sonnet)
              │
              ▼
    Citation Validator    ← every claim maps to retrieved chunk_id, or REJECT
              │
              ▼
    RAGResponse           ← answer + confidence + citations[] + top_signals[] + recommended_action
```

**Grounding corpus (5 doc_types):**
`signal_snapshot` · `explanation` · `policy` · `reviewer_note` · `audit`

> **Note:** RAG v1 (MVP) = SQL + vector over signals/policies/classifications. Similar-domain k-NN search is RAG v2 (Production).

---

## Slide 12: RAG — Response Contract & Anti-Hallucination

**Response contract (every answer must include all fields):**

```json
{
  "answer": "This domain is classified as MFA_High (score: 0.962)...",
  "confidence": "high | medium | low | insufficient",
  "citations": [
    { "source": "signal_snapshot", "id": "sig-abc123", "excerpt": "..." },
    { "source": "policy",          "id": "pol-mfa-001", "excerpt": "..." }
  ],
  "top_signals": [
    { "name": "ad_to_content_ratio", "value": 0.78, "contribution": 0.58 }
  ],
  "recommended_action": "block | allow | recheck | human_review",
  "limitations": "Evidence is based on a single crawl snapshot..."
}
```

**Anti-hallucination pipeline (4 steps):**
1. **Retrieve-first** — no generation without evidence pack
2. **Citation validator** — every claim must map to a `citations[].id` from the retrieved pack
3. **Score threshold** — retrieval score < threshold → respond `insufficient` + `human_review`
4. **Conflict handling** — contradicting signals → present both sides; default to `human_review`

**Cost controls:**
- Cache grounded responses 24h keyed by `evidence_hash`
- Token caps per query
- Batch off-peak for bulk indexing

---

## Slide 13: Risk & Guardrail Design

| Risk | Severity | Control | Status |
|------|----------|---------|--------|
| **Hallucination** | High | Retrieve-first; citation validator; structured output schema | MVP |
| **Prompt injection** | High | Input sanitiser; system prompt isolation; whitelisted tool calls | MVP |
| **False positives** | High | Tiered output; HITL for Medium/Uncertain; page-level scoring | Designed |
| **False negatives** | High | Re-crawl schedule; reviewer feedback loop; drift alerts | MVP |
| **Data leakage** | High | Tenant isolation; RBAC; PII scrubbing; no cross-advertiser sharing | MVP |
| **Reviewer override abuse** | Medium | Mandatory reason code; dual-control for bulk block; audit trail | Designed |
| **Auditability** | High | Immutable audit log; `evidence_hash` on every event; 7-year retention | Designed |
| **Cost runaway** | Medium | Crawl budget per domain; LLM token caps; 24h explanation cache | MVP |
| **Crawler abuse** | Medium | Robots.txt respect; rate limits; user-agent identification | Designed |

**Key security boundaries:**
- LLM never in the classification path
- No open web browsing for LLM in MVP
- Never follow instructions embedded in crawled page content

---

## Slide 14: Reviewer Override Protocol & Audit

**Override workflow — ML score is never deleted**

```
Reviewer sees: tier=MFA_High, score=0.962, confidence=high
      │
      ▼
Selects override_reason (mandatory enum):
  • false_positive_publisher
  • referral_delta_expected
  • policy_exception
  • insufficient_evidence
  • vendor_disagreement
      │
      ▼
Submits final_label (e.g. Non_MFA) + reviewer_notes
      │
      ▼
System stores:
  ml_tier=MFA_High  +  ml_score=0.962  +  final_label=Non_MFA
  (ML score preserved for retraining and audit)
      │
      ▼
Audit event written (append-only)
```

**Audit event contract (immutable):**
- `event_id` · `entity_type` · `entity_id` · `action` · `actor_id`
- `occurred_at` · `evidence_hash` · `payload` (JSONB)
- Append-only — no updates or deletes permitted
- `evidence_hash` binds the audit record to the exact crawl evidence

**Dual-control:** Bulk block operations require a second reviewer sign-off (Production gate)

---

## Slide 15: MVP vs Production Roadmap

| Capability | Baseline ✅ Done | MVP 🟡 In Progress | Production 🔵 Planned |
|------------|-----------------|--------------------|-----------------------|
| Single-persona crawl | ✅ | — | — |
| Dual-persona + 60s refresh | — | ✅ Sprint S1-S2 | — |
| Rules + XGBoost scoring | ✅ | Calibration upgrade | Auto-retrain monthly |
| Template explanations | ✅ | LLM explanations (Bedrock) | — |
| REST API | ✅ All endpoints | — | Pre-bid API (<200ms) |
| RAG Bot | — | v1: SQL + vector | v2: similar-domain k-NN |
| Reviewer console | — | ✅ Sprint S5 | Full SSO/RBAC |
| Audit log | Basic | v1 immutable | 7-year retention |
| OpenSearch vector store | — | ✅ Sprint S4 | Multi-region |
| QuickSight dashboard | — | ✅ Sprint S5 | — |
| Model drift monitoring | — | — | ✅ Production |
| Multi-region DR | — | — | ✅ Production |

**Intentionally excluded from MVP:**
Sub-second pre-bid · Mobile/CTV MFA · Auto-retraining · Multi-tenant SaaS · Federated learning

---

## Slide 16: MVP Sprint Plan

**6 sprints × 2 weeks = 12-week MVP execution**

| Sprint | Focus | Key Deliverables |
|--------|-------|-----------------|
| **S1** (Wk 1–2) | Infrastructure foundation | Terraform (RDS, S3, SQS, ECS), dual-persona crawl, Redis cache |
| **S2** (Wk 3–4) | Crawl upgrade + feature expansion | 60s refresh dwell, schema v2, `referral_direct_delta_score`, calibrator |
| **S3** (Wk 5–6) | Scoring + HITL + LLM explanations | Review queue API, Bedrock explanations, override endpoint, blocklist export |
| **S4** (Wk 7–8) | RAG v1 | OpenSearch index, indexing worker, query router, evidence packager, citation validator, `POST /api/v1/chat` |
| **S5** (Wk 9–10) | Review console + auth | React frontend, queue UI, override workflow, bot chat UI, Cognito/RBAC |
| **S6** (Wk 11–12) | Pilot + shadow mode | Shadow mode runbook, DSP batch ingestion, advertiser pilot sign-off, security review |

**Parallel agent tracks (S1 example):**
- Track A (infra): Terraform modules, S3 IAM
- Track B (crawler): dual-persona config, refresh dwell
- Track C (backend): Redis compose, queue migration

> **Note:** Security review gate (mfa-security-reviewer) required before MVP-2.4 (LLM explanations) and MVP-3.6 (chat API) merge.

---

## Slide 17: Cloud Service Mapping (AWS / Azure / GCP)

| Capability | AWS (Primary) | Azure | GCP |
|------------|--------------|-------|-----|
| API / Auth | API Gateway + Cognito | API Management + Entra ID | Cloud Endpoints + Identity Platform |
| Batch orchestration | Step Functions + EventBridge | Data Factory + Logic Apps | Cloud Composer (Airflow) |
| Stream ingestion | Kinesis → Lambda | Event Hubs | Pub/Sub + Dataflow |
| Crawler workers | ECS Fargate + SQS | Container Apps / AKS | Cloud Run / GKE |
| Object storage | S3 | Blob Storage | Cloud Storage |
| Signal / classification DB | RDS PostgreSQL | Azure Database for PostgreSQL | Cloud SQL PostgreSQL |
| Hot cache | ElastiCache Redis | Azure Cache for Redis | Memorystore Redis |
| Vector / hybrid search | OpenSearch Serverless | Azure AI Search | Vertex AI Vector Search |
| LLM | Bedrock (Claude) | Azure OpenAI Service | Vertex AI (Gemini) |
| Dashboards | QuickSight | Power BI | Looker |
| Immutable audit | DynamoDB + S3 Object Lock | Cosmos DB + Immutable Blob | BigQuery + Cloud Logging |
| Secrets | Secrets Manager + KMS | Key Vault | Secret Manager + Cloud KMS |
| WAF / DDoS | WAF + Shield | Azure DDoS + Front Door | Cloud Armor |

---

## Slide 18: Scale Plan

| Tier | Volume | Architecture Adjustment |
|------|--------|------------------------|
| **Pilot** | 50K–500K URLs/mo | Single-region; 5–10 ECS crawlers; batch nightly; Postgres sufficient |
| **Growth** | 500K–5M URLs/mo | Auto-scaling crawler fleet; tiered crawl depth; aggressive Redis caching; read replicas |
| **Enterprise** | 5M–50M+ URLs/mo | Multi-region; domain-level crawl dedup; approximate scoring for known domains; separate hot/warm/cold SQS queues; pre-computed domain risk cache for <200ms pre-bid API |

**Queue strategy:**
- **SQS Standard** (batch) — full crawl + full feature extraction, nightly inventory
- **SQS FIFO priority** (near-real-time) — shortened crawl, article page only, <2–5 min SLA
- **Redis cache** — domain tier lookup, 24h TTL, used by pre-bid API (<200ms)

**Cost at scale:**
- 500K URLs/mo pilot: **~$8K–$23K/mo** (AWS)
- 5M URLs/mo growth: **~$40K–$90K/mo** (crawler-dominated)
- LLM cost ($2K–$6K/mo) mitigated by 24h evidence_hash cache

---

## Slide 19: Estimation — Team, Timeline, Cost

**Team (peak during MVP: ~7–8 FTE)**

| Role | FTE | Phase |
|------|-----|-------|
| Lead / Solution Architect | 0.5 | POC → Prod |
| Backend / Platform Engineers | 2.0 | POC → Prod |
| ML Engineer | 1.0 | POC → Prod |
| Data Engineer | 1.0 | MVP → Prod |
| Frontend (Review UI + Bot) | 1.0 | MVP → Prod |
| DevOps / SRE | 0.5 | MVP → Prod |
| Ad Ops SME / QA | 0.5 | POC → Prod |
| Product Manager | 0.5 | All |

**Timeline:**
- POC: 6–8 weeks ✅ Done
- MVP: +10–12 weeks (in progress)
- Production: +12–16 weeks
- **Total: ~8–9 months end-to-end**

**Key dependencies:**
Labeled MFA dataset · DSP feed access · Legal crawl approval · Ad Ops workflow adoption · Verification vendor API

---

## Slide 20: Working Code — Key Components

**Real codebase (POC complete as of 2026-07-10)**

`classify_snapshot()` — `ml/src/mfa_ml/scoring/pipeline.py`:
```python
rule_match = artifacts.rules_engine.evaluate(features)
if rule_match:                              # deterministic short-circuit
    return ClassificationOutput(tier=rule_match.tier, classifier="rules", ...)

raw_proba  = artifacts.classifier.predict_proba([features])[0]
calibrated = artifacts.calibrator.transform([raw_proba])[0]
tier, conf = map_tier(calibrated, conf_score, artifacts.thresholds)
top_signals = artifacts.shap_explainer.explain(features)   # SHAP values
```

`answer_query()` — `backend/src/mfa/rag/service.py`:
```python
query  = sanitize_query(request.query)     # injection guard
intent = classify_intent(query)
chunks = await retrieve_evidence(...)      # SQL + OpenSearch hybrid
if evidence_hash: cached = cache.get(evidence_hash)  # 24h cache
response = build_grounded_response(chunks, query)
response = validate_citations(response, chunks)       # anti-hallucination
await write_audit_event(...)               # immutable audit
```

`compute_evidence_hash()` — `backend/src/mfa/schemas/signals.py`:
```python
canonical = json.dumps(signals, sort_keys=True, separators=(",",":"))
return hashlib.sha256(canonical.encode()).hexdigest()
```

> **Note:** All 11 API endpoints are implemented. Demo script (`demo/end_to_end_demo.py`) runs the full pipeline standalone.

---

## Slide 21: Summary & Next Steps

**Where we are:**
- ✅ POC complete: 16-feature signal schema, rules + XGBoost, all API endpoints, 615 gold-labelled URLs
- 🟡 MVP in progress: dual-persona crawl, RAG v1, review console, Terraform infra

**What this submission demonstrates:**
- Production-oriented architecture across all 8 layers
- 9 ADRs covering every major technical decision
- Comprehensive risk & guardrail design (hallucination, injection, false positives, audit)
- Phased roadmap: Baseline → MVP → Production with exit criteria
- Cost modelling at 500K and 5M URLs/month scale
- Working code walkthrough of `classify_snapshot()`, `answer_query()`, signal schema

**Recommended next steps (MVP kickoff):**
1. Terraform sandbox provisioning (RDS, S3, SQS) — Sprint S1
2. Dual-persona crawler with `referral_direct_delta_score` — Sprint S1
3. LLM explanation wiring (Bedrock Claude Haiku) with security review gate — Sprint S3
4. RAG v1 with OpenSearch + citation validator — Sprint S4
5. Shadow-mode pilot with 1–2 advertisers before enabling blocklist export — Sprint S6

> **Note:** Full architecture report at `submission/report.html`. End-to-end runnable demo at `submission/demo/end_to_end_demo.py`.
