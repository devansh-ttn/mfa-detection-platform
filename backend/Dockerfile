# syntax=docker/dockerfile:1

ARG UV_VERSION=0.6.17

FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv

FROM python:3.12-slim-bookworm AS builder

COPY --from=uv /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY common/ common/
COPY ml/pyproject.toml ml/pyproject.toml
COPY ml/src/ ml/src/
COPY backend/pyproject.toml backend/pyproject.toml
COPY backend/src/ backend/src/

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --package mfa-backend --no-dev --no-editable

FROM python:3.12-slim-bookworm AS runtime

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

COPY --from=builder /app/.venv /app/.venv
COPY backend/alembic.ini backend/alembic.ini
COPY backend/alembic/ backend/alembic/
COPY backend/docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
