# MFA Platform — Terraform (MVP-1.1)

Infrastructure foundation for the MFA detection platform: **RDS PostgreSQL 16**, **S3 evidence bucket**, **SQS batch + priority queues**, and **ECS cluster with task definition stubs**.

Naming convention: `mfa-{env}-{service}` (e.g. `mfa-dev-batch-queue`, `mfa-dev-priority-queue.fifo`).

## Prerequisites

- [Terraform](https://www.terraform.io/downloads) >= 1.5
- AWS CLI configured (`aws configure` or SSO)
- IAM permissions to create RDS, S3, SQS, ECS, IAM roles, and CloudWatch Logs
- Default VPC with subnets in the target region (dev uses the account default VPC)

## AWS hardening (post local MVP exit)

After local pilot and shadow mode sign-off:

1. Enable remote Terraform state in `versions.tf`
2. Apply `infra/terraform/` in `dev` with real ECR images
3. Set `SQS_CRAWL_QUEUE_URL` / `SQS_SCORE_QUEUE_URL` — workers consume SQS with Postgres fallback (`sqs_transport.py`)
4. Wire `S3EvidenceStore` + signed URL proxy (MVP-1.2)
5. Deploy OpenSearch Serverless + `indexer-worker` (MVP-3.1/3.2) — `modules/opensearch`, `mfa.rag.worker`
6. Cognito user pool + JWT middleware (MVP-4.6) — `infra/terraform/modules/cognito`, `backend/src/mfa/auth/cognito.py`
7. Shadow mode 4 weeks (`MFA_SHADOW_MODE=1`) then MVP-5.4 AWS checklist sign-off

Application stubs ready: `SqsQueueBackend` in `backend/src/mfa/ingestion/queue.py`, `S3EvidenceStore` in `backend/src/mfa/storage/evidence_store.py`.

## Layout

```
infra/terraform/
├── main.tf              # Root module wiring
├── variables.tf
├── outputs.tf
├── versions.tf
├── modules/
│   ├── rds/             # PostgreSQL 16
│   ├── s3/              # Evidence bucket + versioning
│   ├── sqs/             # Standard batch + FIFO priority
│   ├── ecs/             # Cluster + task definition stubs
│   └── cognito/         # User pool, SPA client, RBAC groups
└── environments/
    └── dev/
        └── terraform.tfvars.example
```

## Apply (dev)

```bash
cd infra/terraform

cp environments/dev/terraform.tfvars.example environments/dev/terraform.tfvars
# Edit terraform.tfvars if needed (region, instance class, tags)

terraform init
terraform plan -var-file=environments/dev/terraform.tfvars
terraform apply -var-file=environments/dev/terraform.tfvars
```

After apply, capture outputs for downstream tasks:

```bash
terraform output -json
```

Key outputs: `rds_endpoint`, `evidence_bucket_name`, `batch_queue_url`, `priority_queue_url`, `ecs_cluster_name`, `cognito_user_pool_id`, `cognito_app_client_id`, `cognito_hosted_ui_domain`.

## Remote state (recommended before shared use)

Uncomment and configure the `backend "s3"` block in `versions.tf`:

- State bucket: `mfa-{env}-terraform-state`
- Lock table: DynamoDB with `LockID` hash key
- Separate state per environment (`dev`, `staging`, `prod`)

Do not commit `.tfstate` files or `terraform.tfvars` with secrets.

## Local development parity

Docker Compose at the repo root mirrors production service boundaries without AWS credentials for the default path.

| AWS (Terraform) | Local (Compose) | Notes |
|-----------------|-----------------|-------|
| RDS PostgreSQL 16 | `postgres` service (`postgres:16-alpine`) | `DATABASE_URL` on API/workers |
| ElastiCache Redis | `redis` service (`redis:7-alpine`) | `REDIS_URL=redis://redis:6379/0` |
| S3 evidence bucket | `localstack` profile + volume, or `./backend/evidence` mount | Enable with `docker compose --profile localstack up` |
| SQS batch + FIFO | LocalStack SQS on `:4566` | Set `AWS_ENDPOINT_URL=http://localstack:4566` when profile active |
| ECS Fargate services | `backend-api`, `crawler-worker`, `ml-worker` | Workers under `--profile workers` |

### Compose quick start

```bash
# API + Postgres + Redis (no AWS)
docker compose up -d postgres redis backend-api

# Workers
docker compose --profile workers up -d

# Optional LocalStack for S3/SQS
docker compose --profile localstack up -d
```

### LocalStack queue/bucket bootstrap (manual)

After LocalStack is healthy, create resources matching Terraform names:

```bash
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION=us-east-1
ENDPOINT=http://localhost:4566

aws --endpoint-url=$ENDPOINT s3 mb s3://mfa-local-evidence
aws --endpoint-url=$ENDPOINT sqs create-queue --queue-name mfa-local-batch-queue
aws --endpoint-url=$ENDPOINT sqs create-queue \
  --queue-name mfa-local-priority-queue.fifo \
  --attributes FifoQueue=true,ContentBasedDeduplication=true
```

Use `ENV=local` in application config (not a Terraform deploy environment).

## Handoffs

| Output | Consumer | Task |
|--------|----------|------|
| `evidence_bucket_name` | `mfa-backend-engineer` | Signed URL proxy (MVP-1.2) |
| `batch_queue_url`, `priority_queue_url` | `mfa-backend-engineer` | Queue migration from Postgres poll (MVP-1.3) |
| `rds_endpoint` | All services | Connection strings via Secrets Manager |
| ECS task defs | CI/CD | Replace stub images with ECR builds |

## Cost notes (dev)

Approximate monthly dev footprint (us-east-1, single-AZ):

| Resource | Dev sizing | Est. |
|----------|------------|------|
| RDS `db.t4g.medium` | 20 GiB gp3 | ~$50–70 |
| S3 evidence | Low volume + versioning | ~$1–5 |
| SQS | Pay per request | <$1 |
| ECS | Cluster free; tasks billed when running | $0 until services deployed |
| CloudWatch Logs | 7-day retention | ~$1–5 |

Scale tiers and production adjustments: `docs/ARCHITECTURE.md` and `.cursor/rules/mfa-infra-aws.mdc`.

## Security

- RDS is **not** publicly accessible; ingress limited to VPC CIDR
- S3 public access blocked; encryption at rest enabled
- No account IDs or secrets in `.tf` files
- RDS master password managed by AWS (`manage_master_user_password`)
