# MFA Review Console (Frontend)

Minimal React + TypeScript frontend for the MFA detection platform reviewer console and RAG chat (MVP-4).

## Prerequisites

- Node.js 20+
- Backend API running (see repo root `docs/LOCAL_DEV_GUIDE.md`)

## Setup

```bash
cd frontend
npm install
cp .env.local.example .env.local   # optional — enables Vite `/api` proxy
```

## Local development

Start the API stack (from repo root):

```bash
docker compose up -d postgres redis backend-api crawler-worker ml-worker
uv run python scripts/seed/seed_reviewer_demo.py   # demo queue rows for E2E
```

Start the Vite dev server (proxies `/api` to the backend):

```bash
npm run dev
```

Open [http://localhost:5173](http://localhost:5173).

### Dev auth (RBAC)

**Local (no Cognito env vars):** pick a role and actor on the dev login screen. Headers `X-MFA-Role` / `X-MFA-Actor` are sent on each request.

**Deployed (MVP-4.6):** set Cognito env vars in `frontend/.env.local` (see `.env.local.example`). The console uses Cognito hosted UI (OIDC + PKCE) and sends `Authorization: Bearer <id_token>`. Roles come from Cognito groups matching MFA role names.

Backend env (ECS / Compose):

```env
COGNITO_USER_POOL_ID=us-east-1_XXXXXXXXX
COGNITO_APP_CLIENT_ID=xxxxxxxxxxxxxxxxxxxxxxxxxx
COGNITO_REGION=us-east-1
MFA_REQUIRE_AUTH=1   # or ENV=prod
```

Provision pool + groups via `infra/terraform` (`module.cognito` outputs).

| Role | Review queue | Override | Chat | Blocklist |
|------|--------------|----------|------|-----------|
| reviewer | yes | yes | yes | no |
| admin, ad_ops | yes | yes | yes | yes |
| auditor | yes | no | yes | yes |
| read_only | no | no | yes | no |

Use **Switch user** in the header to change role. Forbidden API responses show a clear 403 message.

### API base URL

By default, `VITE_API_URL` is unset and requests use same-origin `/api` (Vite dev proxy → `http://localhost:8000`).

To call the API directly (e.g. no proxy), set in `.env.local`:

```env
VITE_API_URL=http://localhost:8000
```

For Docker Compose, the `frontend` service sets `VITE_PROXY_TARGET=http://backend-api:8000`.

## E2E walkthrough

With stack + seed data running:

1. **Review Queue** — filter by tier/domain; click **Detail**
2. **Detail** — signal bar chart, evidence thumbnails, audit sidebar; **Submit override** (reviewer/admin/ad_ops only)
3. **Override** — classification ID pre-filled; submit with required reason code
4. **Blocklist** — ad_ops/auditor: filter MFA_High entries
5. **Chat** — query a domain; confirm citations render

See `docs/LOCAL_DEV_GUIDE.md` §6.4 for the full path.

## Docker Compose (full stack)

From repo root:

```bash
docker compose up -d --build
```

Frontend: [http://localhost:5173](http://localhost:5173) · API: [http://localhost:8000](http://localhost:8000)

Seed demo queue rows (host, against compose Postgres):

```bash
uv run python scripts/seed/seed_reviewer_demo.py
```

## Pages

| Page | API |
|------|-----|
| Review Queue | `GET /api/v1/reviews/queue` |
| Override | `POST /api/v1/reviews` |
| Chat | `POST /api/v1/chat` |
| Blocklist | `GET /api/v1/blocklist` |
| Detail — audit | `GET /api/v1/audit?url_id=` |
| Detail — evidence | `GET /api/v1/urls/{url_id}/evidence` |

## Build

```bash
npm run build
npm run preview
```

Set `VITE_API_URL` to your deployed API origin before building for production.
