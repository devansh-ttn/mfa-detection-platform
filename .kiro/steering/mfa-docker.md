---
inclusion: fileMatch
fileMatchPattern: ['**/Dockerfile*', '**/docker-compose*.yml', '**/.dockerignore']
---

# MFA Platform — Docker rules

Reference: **`.cursor/skills/mfa-docker/SKILL.md`**, `docs/LOCAL_DEV_GUIDE.md`, `.cursor/rules/mfa-infra-aws.mdc`

## Build context

- All app images build from **repo root** (`context: .`) — optimize root `.dockerignore` first
- Never send `.git`, `data/`, `ml/artifacts/`, `**/tests`, or local venvs to the daemon

## Base images (required)

| Service | Base | Notes |
|---------|------|-------|
| `backend-api`, `ml-worker` | `python:3.12-slim-bookworm` | Pin digest or patch tag in production |
| `crawler-worker` | `python:3.12-slim-bookworm` | **Not Alpine** — Playwright/Chromium need Debian glibc |
| `postgres` | `postgres:16-alpine` | Already minimal |
| `uv` CLI | `ghcr.io/astral-sh/uv:<version>` | Pin version; never `:latest` in committed Dockerfiles |

## uv workspace installs

- Use `uv sync --frozen --package <mfa-package> --no-dev --no-editable` — no ad hoc `pip install`
- `COPY` only workspace members in the dependency graph (see skill cheat sheet)
- Do **not** copy `crawler/` into `backend/Dockerfile` — `mfa-backend` does not depend on it
- Copy lockfiles + manifests before source; run `uv sync` before service-specific `COPY`

## Crawler-specific

- Playwright browser install only in `crawler/Dockerfile`
- Chain `playwright install-deps chromium` + `playwright install chromium` in the same `RUN` as `uv sync`
- Do not add Chromium layers to API or ML images

## ML artifacts

- Do not bake `ml/artifacts/` into images for local dev — mount via Compose or set `ARTIFACT_DIR`
- Production artifact loading from S3 → TODO(MVP)

## Compose

- Keep worker services under `profiles: ["workers"]`
- Pin third-party image tags; use healthchecks + `depends_on` (existing pattern)
- Secrets via env / Secrets Manager — never `COPY .env`

## Do not

- Switch crawler to Alpine or distroless without proven Playwright support
- Include dev dependency groups in production `uv sync`
- Run crawl or ML scoring inside the API container
- Use unpinned `:latest` base images in committed Dockerfiles
