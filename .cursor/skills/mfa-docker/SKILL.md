---
name: mfa-docker
description: Audits and optimizes Dockerfiles, Docker Compose, and build contexts for the MFA uv monorepo. Use when changing container images, reducing image size or build time, or adding a new service to docker-compose.yml.
---

# MFA Docker Image Optimization

Reference: `.cursor/rules/mfa-docker.mdc` · `docker-compose.yml` · `docs/ARCHITECTURE.md` · `docs/LOCAL_DEV_GUIDE.md`

## Stack context

| Service | Dockerfile | Base | Special runtime needs |
|---------|------------|------|------------------------|
| `backend-api` | `backend/Dockerfile` | `python:3.12-slim-bookworm` | FastAPI + Alembic migrations |
| `crawler-worker` | `crawler/Dockerfile` | `python:3.12-slim-bookworm` | Playwright Chromium + OS deps |
| `ml-worker` | `ml/Dockerfile` | `python:3.12-slim-bookworm` | XGBoost/numba; model artifacts at runtime |
| `postgres` | upstream | `postgres:16-alpine` | data volume only |

**Build context is always the repo root** (`context: .` in Compose). Service Dockerfiles live under `backend/`, `crawler/`, or `ml/`.

**Package manager:** [uv](https://docs.astral.sh/uv/) workspace (`pyproject.toml` + `uv.lock` at root). Never `pip install` directly in Dockerfiles.

**Workspace dependency graph** (determines minimal `COPY` set):

```
mfa-backend  → mfa-common, mfa-ml
mfa-crawler  → mfa-common, mfa-backend (transitively mfa-ml)
mfa-ml       → mfa-common
```

---

## Analysis protocol

Run this checklist whenever auditing or refactoring containers.

### 1. `.dockerignore` audit (repo root)

Confirm heavy assets never enter the build daemon context:

- `.git`, `.github`, `.cursor`, `.vscode`, `.idea`
- Virtualenvs: `.venv/`, `venv/`, `**/.venv`
- Caches: `**/__pycache__`, `**/.pytest_cache`, `**/.ruff_cache`, `**/.mypy_cache`
- Tests: `**/tests/`, `coverage/`
- Local data: `data/`, `backend/evidence/`
- Docs & plans: `docs/`, `*.md` (except files explicitly needed)
- Frontend (not containerized yet): `frontend/`
- Infra: `infra/terraform/.terraform`
- Secrets: `.env`, `.env.*` (keep `!.env.example`)
- Training outputs not needed at runtime: `ml/scripts/`, `**/*.pkl`, large local experiment dirs
- `ml/artifacts/` — exclude from context; mount or explicit `COPY` at runtime (see §7)

**Do not exclude** files a Dockerfile `COPY`s: root `pyproject.toml`, `uv.lock`, workspace `pyproject.toml` + `src/` trees for installed packages.

Target build context **< 5 MB** (before `.venv` layer). Verify with `docker compose build --progress=plain` and inspect "transferring context" size.

### 2. Base image rules

| Rule | MFA choice |
|------|------------|
| Pin Python | `python:3.12-slim-bookworm` (not `latest`, not full `python:3.12`) |
| Pin uv binary | `ghcr.io/astral-sh/uv:0.6.x` — avoid `:latest` in production Dockerfiles |
| Crawler OS | Stay on **Debian slim**, not Alpine — Playwright `install-deps` needs glibc + apt packages |
| Postgres | `postgres:16-alpine` (already minimal) |
| Distroless | **Not yet** — Playwright and Alembic shell entrypoints need a full slim runtime |

### 3. uv workspace COPY minimization

Copy only what the target package needs to resolve and build workspace deps:

| Image | Install package | Required COPY (minimum) |
|-------|-----------------|-------------------------|
| `backend-api` | `mfa-backend` | root lockfiles, `common/`, `ml/pyproject.toml` + `ml/src/`, `backend/` — **not** `crawler/` |
| `crawler-worker` | `mfa-crawler` | root lockfiles, `common/`, `backend/pyproject.toml` + `backend/src/`, `ml/pyproject.toml` + `ml/src/`, `crawler/` |
| `ml-worker` | `mfa-ml` | root lockfiles, `common/`, `ml/` — **not** `backend/` or `crawler/` (+ `COPY ml/artifacts/v1/` when scoring ships) |

Avoid copying sibling packages' `tests/`, `scripts/`, or full trees when only `pyproject.toml` + `src/` are required.

**Known bloat (fix when touching Dockerfiles):** `backend/Dockerfile` currently copies full `crawler/` even though `mfa-backend` has no crawler dependency. All three Dockerfiles use `ghcr.io/astral-sh/uv:latest` — pin to a specific release (e.g. `0.6.17`).

### 4. Layer optimization

- Combine `apt-get` / Playwright install in **one** `RUN` and clean apt lists in the same layer:
  ```dockerfile
  RUN uv sync --frozen --package mfa-crawler --no-dev \
      && uv run --package mfa-crawler playwright install-deps chromium \
      && uv run --package mfa-crawler playwright install chromium \
      && rm -rf /var/lib/apt/lists/*
  ```
- Set env vars once: `UV_COMPILE_BYTECODE=1`, `UV_LINK_MODE=copy`, `PYTHONUNBUFFERED=1`
- Order Dockerfile: lockfiles → workspace manifests → `uv sync` → application `src/` last (max cache hits)
- Use BuildKit cache mounts for uv (optional, high impact on rebuilds):
  ```dockerfile
  RUN --mount=type=cache,target=/root/.cache/uv \
      uv sync --frozen --package mfa-backend --no-dev
  ```

### 5. Multi-stage pattern (backend + ml)

Separate dependency install from runtime. Crawler uses the same builder/runtime split; Playwright installs in the runtime stage only.

```dockerfile
# syntax=docker/dockerfile:1

ARG UV_VERSION=0.6.17
FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv

FROM python:3.12-slim-bookworm AS builder
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
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
```

Runtime stage drops the `uv` binary and build-only workspace files. **`--no-editable` is required** — default workspace sync writes `.pth` pointers to `/app/*/src`, which are absent in the runtime stage. Pin uv via a dedicated `FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv` stage.

### 6. Crawler-specific constraints

- **Never** switch crawler to Alpine without replacing Playwright's browser stack.
- Install **Chromium only** (`playwright install chromium`) — not all browsers.
- `crawler-worker` needs `backend/src/` because `mfa-crawler` depends on `mfa-backend` (job poll / DB models).
- ECS/Fargate: target image &lt; 1.5 GB compressed; Chromium dominates — focus on excluding tests/docs from context, not removing browser.

### 7. ML worker artifacts

When `mfa_ml.worker` loads models:

```dockerfile
COPY ml/artifacts/v1/ ml/artifacts/v1/
```

Or inject via `ML_ARTIFACT_DIR` volume / S3 download at startup (preferred for Production). Do not bake training notebooks, `ml/scripts/`, or experiment dirs into the image.

### 8. Compose hygiene

- Keep `postgres:16-alpine` with healthcheck (already correct).
- Worker services under `profiles: ["workers"]` — default `docker compose up` stays API + DB only.
- Use `ENV=local` in Compose; never mount `.env` with production secrets into images.
- Pin image tags in Compose for third-party services; app services use `build:` not mutable tags.

---

## Response format (required)

When analyzing or proposing Dockerfile changes, respond with:

1. **Size audit & key issues** — bullet list of bloat, missing ignores, over-copied workspace paths, unpinned bases.
2. **Optimized Dockerfile(s)** — complete file(s) per affected service.
3. **Recommended `.dockerignore`** — repo-root ignore deltas (not full file unless asked).
4. **Estimated reduction** — approximate MB or % saved and which change drives it.

Validate proposals:

```bash
docker compose build
docker compose --profile workers build
docker images | grep mfa
```

---

## Python / uv cheat sheet (this repo)

| Anti-pattern | Recommended | Why |
|--------------|-------------|-----|
| `python:3.12` (~1 GB) | `python:3.12-slim-bookworm` (~150 MB) | Already in use; keep pinned |
| `uv:latest` | `ghcr.io/astral-sh/uv:0.6.x` | Reproducible builds |
| Alpine for crawler | Debian slim + Playwright | Chromium needs glibc + apt deps |
| `pip install -r requirements.txt` | `uv sync --frozen --package … --no-dev` | Workspace monorepo standard |
| Full monorepo `COPY` | Dependency-graph minimal COPY | Faster context + cache |
| Distroless (all services) | Slim runtime; optional multi-stage for API/ML | Playwright + Alembic entrypoint need shell |

---

## Do not

- Use `python:3.12` full image or `ubuntu:latest` bases
- Run `playwright install` without `install-deps` on Debian slim
- Copy `.git`, `data/seed/`, test suites, or `.env` into images
- Copy `crawler/` into `backend/Dockerfile` (not in dependency graph)
- Add `npm install` / `pip install` outside `uv sync`
- Remove Alembic `entrypoint.sh` or migration files from `backend-api`
- Switch crawler to distroless/Alpine without a verified Playwright alternative
- Commit ad-hoc `ml/artifacts/` experiments — only versioned production artifacts belong in images
