#!/usr/bin/env bash
# Create LocalStack SQS queues for MVP-1.3 dev parity.
set -euo pipefail

ENDPOINT="${AWS_ENDPOINT_URL:-http://localhost:4566}"
REGION="${AWS_DEFAULT_REGION:-us-east-1}"
PREFIX="${MFA_QUEUE_PREFIX:-mfa-local}"

export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION="$REGION"

aws --endpoint-url="$ENDPOINT" sqs create-queue \
  --queue-name "${PREFIX}-batch-queue" \
  --attributes VisibilityTimeout=300,ReceiveMessageWaitTimeSeconds=5 \
  2>/dev/null || true

aws --endpoint-url="$ENDPOINT" sqs create-queue \
  --queue-name "${PREFIX}-priority-queue.fifo" \
  --attributes FifoQueue=true,ContentBasedDeduplication=true,VisibilityTimeout=300 \
  2>/dev/null || true

BATCH_URL="$(aws --endpoint-url="$ENDPOINT" sqs get-queue-url --queue-name "${PREFIX}-batch-queue" --query QueueUrl --output text)"
PRIORITY_URL="$(aws --endpoint-url="$ENDPOINT" sqs get-queue-url --queue-name "${PREFIX}-priority-queue.fifo" --query QueueUrl --output text)"

cat <<EOF
LocalStack SQS queues ready.

Add to .env:
  AWS_ENDPOINT_URL=$ENDPOINT
  SQS_BATCH_QUEUE_URL=$BATCH_URL
  SQS_CRAWL_QUEUE_URL=$BATCH_URL
  SQS_SCORE_QUEUE_URL=$BATCH_URL
  SQS_PRIORITY_QUEUE_URL=$PRIORITY_URL
EOF
