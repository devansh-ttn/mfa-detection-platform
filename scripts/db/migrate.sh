#!/usr/bin/env bash
# Run Alembic migrations from repo root (alembic.ini lives in backend/).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
exec uv run --directory backend alembic "$@"
