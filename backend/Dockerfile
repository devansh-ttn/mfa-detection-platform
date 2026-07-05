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
COPY crawler/ /app/crawler/
COPY backend/pyproject.toml /app/backend/pyproject.toml

RUN uv sync --frozen --package mfa-backend --no-dev

COPY backend/alembic.ini /app/backend/
COPY backend/alembic/ /app/backend/alembic/
COPY backend/src/ /app/backend/src/
COPY backend/docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
