# MFA Platform — Architecture

## Layers

| Layer | Components | Key outputs |
|-------|------------|-------------|
| **Ingestion** | API, batch orchestrator, event processor, URL dedup | `url_id`, crawl job, priority queue |
| **Signal extraction** | Headless crawler, vision, DOM parser, metadata enricher, traffic analyzer | Feature vector + evidence artifacts |
| **Stores** | Postgres (signals), S3 (artifacts), OpenSearch (vectors), Redis (cache), audit log | Versioned snapshots |
| **AI/ML** | Rules engine, XGBoost ensemble, LLM explanations, calibrator, HITL router | `tier`, `mfa_score`, `confidence`, `top_signals` |
| **RAG** | Chat gateway, safety filter, query router, hybrid retriever, citation validator | Cited answers + recommended action |
| **UI** | Reviewer console, ops dashboards, bot UI, blocklist export | Overrides, exports, alerts |

## Data flow

```
DSP/SSP inventory → Ingestion → Crawler (dual-persona, 60s dwell)
  → Feature store (Postgres JSONB + S3 artifacts)
  → Rules → ML ensemble → Calibrator
  → [confidence OK] → explanation → export/dashboard
  → [low confidence / high spend] → HITL review queue
RAG queries → hybrid SQL + OpenSearch retrieval → grounded LLM → citation validator
```

## Near-real-time vs batch

- **Batch:** nightly inventory sweep (millions of URLs) via Step Functions
- **Near-real-time:** SQS priority queue for new placements; &lt;2–5 min SLA using cached domain signals + incremental crawl

## Integration points

| Direction | Interface |
|-----------|-----------|
| Inbound | DSP CSV/S3 export, REST API, webhook, optional OpenRTB log sink (Kinesis) |
| Outbound | Blocklist API, pre-bid segment push, BI facts, Slack high-spend alerts |
| Enrichment | Verification vendor traffic signals (one signal, not source of truth) |

## AWS service map (primary)

API Gateway + Cognito · Step Functions + EventBridge · Kinesis → Lambda · ECS Fargate + SQS · RDS PostgreSQL · ElastiCache Redis · OpenSearch Serverless · S3 · Bedrock · DynamoDB audit · Secrets Manager + KMS · WAF + Shield

Full plan: `.cursor/plans/mfa_platform_architecture_48645023.plan.md` Section 8.
