"""Smoke test — navigate a URL and print or persist SignalSnapshotPayload JSON."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid

import structlog
from mfa_common.logging import configure_logging

from mfa_crawler.crawl import crawl_url
from mfa_crawler.persist import crawl_and_persist

logger = structlog.get_logger(__name__)

DEFAULT_SMOKE_URL = "https://example.com"


async def run_smoke(url: str = DEFAULT_SMOKE_URL) -> dict:
    result = await crawl_url(url)
    doc = result.payload.to_db()
    logger.info(
        "crawl_smoke_ok",
        url=url,
        duration_sec=round(result.duration_sec, 3),
        schema_version=doc["schema_version"],
    )
    return doc


async def run_smoke_persist(url_id: uuid.UUID) -> dict:
    result = await crawl_and_persist(url_id)
    doc = result.payload.to_db()
    return {
        "snapshot_id": str(result.snapshot_id),
        "url_id": str(result.url_id),
        "version": result.version,
        "persona": result.persona,
        "evidence_hash": result.evidence_hash,
        "crawl_duration_sec": result.crawl_duration_sec,
        "artifact_dir": str(result.artifact_dir) if result.artifact_dir else None,
        "signals": doc,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Crawl a URL and print or persist signal snapshot JSON")
    parser.add_argument("url", nargs="?", default=DEFAULT_SMOKE_URL, help="URL to crawl (ignored with --persist)")
    parser.add_argument(
        "--persist",
        action="store_true",
        help="Crawl the URL row for --url-id and insert signal_snapshots",
    )
    parser.add_argument(
        "--url-id",
        type=uuid.UUID,
        help="urls.id to persist against (required with --persist)",
    )
    return parser


def main() -> None:
    configure_logging()
    args = _build_parser().parse_args()

    if args.persist and args.url_id is None:
        print("error: --url-id is required when using --persist", file=sys.stderr)
        sys.exit(2)

    try:
        if args.persist:
            doc = asyncio.run(run_smoke_persist(args.url_id))
        else:
            doc = asyncio.run(run_smoke(args.url))
    except Exception:
        logger.exception("crawl_smoke_failed", url=args.url, url_id=str(args.url_id) if args.url_id else None)
        sys.exit(1)

    print(json.dumps(doc, indent=2, default=str))
    sys.exit(0)


if __name__ == "__main__":
    main()
