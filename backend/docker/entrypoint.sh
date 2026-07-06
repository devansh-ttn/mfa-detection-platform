#!/bin/sh
set -e

if [ -n "${DATABASE_URL_SYNC}" ]; then
  echo "Running database migrations..."
  uv run --directory backend alembic upgrade head
fi

echo "Starting API server..."
exec uv run --directory backend uvicorn mfa.main:app --host 0.0.0.0 --port 8000
