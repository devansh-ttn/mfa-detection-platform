# syntax=docker/dockerfile:1

FROM python:3.12-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY common/ /app/common/
COPY ml/ /app/ml/
COPY crawler/pyproject.toml /app/crawler/pyproject.toml
COPY backend/pyproject.toml /app/backend/pyproject.toml

RUN uv sync --frozen --package mfa-ml --no-dev

COPY ml/src/ /app/ml/src/

CMD ["uv", "run", "--package", "mfa-ml", "python", "-m", "mfa_ml.worker"]
