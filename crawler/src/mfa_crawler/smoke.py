"""Smoke test — navigate example.com and print SignalSnapshotPayload JSON."""

from __future__ import annotations

import asyncio
import json
import sys

import structlog
from mfa_common.logging import configure_logging

from mfa_crawler.crawl import crawl_url

logger = structlog.get_logger(__name__)

DEFAULT_SMOKE_URL = "https://example.com"


async def run_smoke(url: str = DEFAULT_SMOKE_URL) -> dict:
    payload, duration_sec = await crawl_url(url)
    doc = payload.to_db()
    logger.info(
        "crawl_smoke_ok",
        url=url,
        duration_sec=round(duration_sec, 3),
        schema_version=doc["schema_version"],
    )
    return doc


def main() -> None:
    configure_logging()
    url = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SMOKE_URL
    try:
        doc = asyncio.run(run_smoke(url))
    except Exception:
        logger.exception("crawl_smoke_failed", url=url)
        sys.exit(1)

    print(json.dumps(doc, indent=2, default=str))
    sys.exit(0)


if __name__ == "__main__":
    main()
