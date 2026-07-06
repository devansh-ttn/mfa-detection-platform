# mfa-common

Shared utilities used by every Python service in the monorepo (backend, crawler, ml).

## Purpose

`mfa-common` keeps cross-cutting concerns in one place so each service stays focused on its own job. Today it provides **structured JSON logging**; more shared helpers (config, tracing) may land here later.

## What it contains

| Module | Purpose |
|--------|---------|
| `mfa_common.logging` | `configure_logging()` — JSON logs via structlog, compatible with uvicorn and workers |

All services call `configure_logging()` at startup so logs look the same in Docker, local dev, and CI.

## How other services use it

```python
from mfa_common.logging import configure_logging

configure_logging(os.getenv("LOG_LEVEL", "INFO"))
```

## Local development

From the repo root:

```bash
uv sync --all-packages
```

You rarely work in this package directly unless you are adding a new shared utility.

## Related docs

- Root overview: [`../README.md`](../README.md)
- Backend: [`../backend/README.md`](../backend/README.md)
