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
COPY backend/pyproject.toml backend/pyproject.toml
COPY backend/src/ backend/src/
COPY ml/pyproject.toml ml/pyproject.toml
COPY crawler/pyproject.toml crawler/pyproject.toml
COPY crawler/src/ crawler/src/

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --package mfa-crawler --no-dev --no-editable

FROM python:3.12-slim-bookworm AS runtime

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

COPY --from=builder /app/.venv /app/.venv

RUN playwright install-deps chromium \
    && playwright install chromium \
    && rm -rf /var/lib/apt/lists/*

CMD ["python", "-m", "mfa_crawler.worker"]
