"""Single-persona crawl orchestration."""

from __future__ import annotations

import time
from datetime import UTC, datetime

from mfa.schemas.signals import SIGNAL_SCHEMA_VERSION, SignalSnapshotPayload

from mfa_crawler.browser import crawl_page, load_crawl_settings
from mfa_crawler.dom_parser import extract_dom_metrics


async def crawl_url(
    url: str,
    *,
    persona: str = "direct",
) -> tuple[SignalSnapshotPayload, float]:
    """Navigate, extract DOM metrics, return validated payload and duration_sec."""
    settings = load_crawl_settings()
    started = time.perf_counter()

    async with crawl_page(url, settings=settings, persona=persona) as page:
        features = await extract_dom_metrics(page)
        crawl_ts = datetime.now(UTC)

    duration_sec = time.perf_counter() - started
    payload = SignalSnapshotPayload(crawl_ts=crawl_ts, features=features)
    assert payload.to_db()["schema_version"] == SIGNAL_SCHEMA_VERSION
    return payload, duration_sec
