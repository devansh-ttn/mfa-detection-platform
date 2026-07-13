#!/usr/bin/env bash
# Start the local Docker stack with optional crawler-worker replicas.
#
# Reads CRAWL_WORKER_REPLICAS from repo-root .env (default 1).
# Example: CRAWL_WORKER_REPLICAS=3 ./scripts/dev/up-stack.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

CRAWL_WORKERS="${CRAWL_WORKER_REPLICAS:-1}"
if ! [[ "$CRAWL_WORKERS" =~ ^[0-9]+$ ]] || [[ "$CRAWL_WORKERS" -lt 1 ]]; then
  echo "ERROR: CRAWL_WORKER_REPLICAS must be a positive integer (got: ${CRAWL_WORKER_REPLICAS:-})" >&2
  exit 1
fi

echo "Starting stack with crawler-worker replicas=${CRAWL_WORKERS}"
exec docker compose up -d --build --scale "crawler-worker=${CRAWL_WORKERS}" "$@"
