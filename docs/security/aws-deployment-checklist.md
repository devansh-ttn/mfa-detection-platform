# AWS deployment security review (MVP-5.4 production path)

**Reviewer:** `mfa-security-reviewer`  
**Scope:** ECS deployment with Cognito, SQS, OpenSearch, S3 evidence, RAG chat  
**Gate:** Required before enabling DSP blocklist enforcement (post shadow mode)

## Pre-deploy checklist

### Identity & access

- [ ] Cognito user pool with MFA roles as groups (`admin`, `reviewer`, `ad_ops`, `auditor`, `read_only`)
- [ ] `MFA_REQUIRE_AUTH=1` or `ENV=prod` on all API/worker tasks
- [ ] No `X-MFA-Role` header auth in production (Cognito Bearer only)
- [ ] ECS task roles: least-privilege S3, SQS, OpenSearch, Bedrock, Secrets Manager
- [ ] RDS security group: ECS tasks only (no `0.0.0.0/0`)
- [ ] OpenSearch Serverless network policy: private for `prod`

### Data protection

- [ ] RDS encryption at rest enabled
- [ ] S3 evidence bucket versioning + block public access
- [ ] TLS 1.2+ on ALB/API Gateway → ECS
- [ ] Secrets in Secrets Manager (DB password, Cognito not in task env plaintext)
- [ ] PII scrubbing in CloudWatch logs verified

### RAG / LLM

- [ ] Input sanitizer on `POST /api/v1/chat`
- [ ] Citation validator enforced; audit per query with `evidence_hash`
- [ ] Bedrock IAM scoped to inference profile only
- [ ] No crawled page instructions in LLM context (signals JSON only)

### Audit & compliance

- [ ] Append-only audit events for classifications, overrides, RAG answers
- [ ] Immutable audit export (MVP-4.5) scheduled to S3 Object Lock bucket
- [ ] Reviewer overrides preserve ML score + mandatory `override_reason`

### Queue & worker security

- [ ] SQS queues not publicly accessible
- [ ] Message bodies contain IDs only (no raw PII URLs in queue payloads where avoidable)
- [ ] Dead-letter queues configured for batch and priority queues
- [ ] Worker tasks cannot reach admin APIs

## Deployment verification

```bash
# Auth — expect 401 without token
curl -s -o /dev/null -w "%{http_code}" https://<api>/api/v1/reviews/queue

# Auth — expect 200 with valid Cognito ID token
curl -s -H "Authorization: Bearer $ID_TOKEN" https://<api>/api/v1/reviews/queue | jq '.total'

# Shadow mode — blocklist returns shadow_mode=true until go-live
curl -s -H "Authorization: Bearer $ID_TOKEN" \
  "https://<api>/api/v1/blocklist?tier=MFA_High&limit=1" | jq '.shadow_mode'
```

## Findings log

| ID | Severity | Finding | Remediation | Status |
|----|----------|---------|-------------|--------|
| AWS-001 | High | API Gateway authorizer optional | JWT validated in FastAPI; add API GW authorizer for defense-in-depth | Open |
| AWS-002 | Medium | OpenSearch data access policy | Attach ECS task role after terraform apply | Open |
| AWS-003 | Medium | SQS DLQ | Add DLQ resources in `modules/sqs` | Open |
| AWS-004 | Low | k-NN embeddings | BM25-only for MVP; k-NN in Production RAG v2 | Accepted |

## Sign-off

```
Reviewer: ____________________
Date: ____________________
Approved for AWS pilot (shadow mode): [ ] Yes  [ ] No
Approved for DSP block enforcement:   [ ] Yes  [ ] No  (requires 4-week shadow + gates)
```
