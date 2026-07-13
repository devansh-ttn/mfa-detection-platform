---
inclusion: fileMatch
fileMatchPattern: ['frontend/**/*']
---

# MFA Platform — Frontend rules

## Stack

Vite + React + TypeScript + TanStack Query. Component library: match existing patterns when introduced.

## Reviewer console

> **TODO(MVP):** Reviewer console — see `docs/ROADMAP.md`

- Queue view: filter by `tier`, `confidence`, `spend_usd` desc
- Detail view: signal breakdown, top_signals chart, explanation, evidence thumbnails
- Override form: `final_label` + required `override_reason` enum + notes
- Audit trail sidebar per URL

## Bot UI

> **TODO(MVP):** Chat UI — see `docs/ROADMAP.md`

- Chat interface with cited responses
- Display `confidence`, `top_signals`, `recommended_action`, `limitations`
- Link citations to signal snapshot detail view

## Patterns

- API client with auth headers; no secrets in frontend bundle
- Optimistic UI only for non-destructive actions
- Loading/error states on all async views
- Accessibility: keyboard nav on review queue

## Do not

- Allow override without reason code
- Render LLM answer text without citation links
- Store API keys in `VITE_*` env vars
