#!/bin/sh
set -e

if [ -n "${DATABASE_URL_SYNC}" ]; then
  echo "Running database migrations..."
  cd /app/backend && alembic upgrade head
fi

echo "Starting API server..."
exec uvicorn mfa.main:app --host 0.0.0.0 --port 8000
