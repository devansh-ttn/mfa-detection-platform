# syntax=docker/dockerfile:1

FROM python:3.12-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY common/ /app/common/
COPY crawler/ /app/crawler/
COPY ml/pyproject.toml /app/ml/pyproject.toml
COPY backend/pyproject.toml /app/backend/pyproject.toml

RUN uv sync --frozen --package mfa-crawler --no-dev

COPY crawler/src/ /app/crawler/src/

CMD ["uv", "run", "--package", "mfa-crawler", "python", "-m", "mfa_crawler.worker"]
