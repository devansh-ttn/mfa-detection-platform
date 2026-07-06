"""Single-persona crawl orchestration."""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, datetime

from mfa.schemas.signals import SignalSnapshotPayload

from mfa_crawler.browser import crawl_page, load_crawl_settings
from mfa_crawler.dom_parser import extract_dom_metrics


@dataclass(frozen=True)
class CrawlResult:
    payload: SignalSnapshotPayload
    duration_sec: float
    html: str
    screenshot_png: bytes


async def crawl_url(
    url: str,
    *,
    persona: str = "direct",
) -> CrawlResult:
    """Navigate, extract DOM metrics and evidence captures, return validated result."""
    settings = load_crawl_settings()
    started = time.perf_counter()

    async with crawl_page(url, settings=settings, persona=persona) as page:
        features = await extract_dom_metrics(page)
        html = await page.content()
        screenshot_png = await page.screenshot(type="png", full_page=True)
        crawl_ts = datetime.now(UTC)

    duration_sec = time.perf_counter() - started
    payload = SignalSnapshotPayload(crawl_ts=crawl_ts, features=features)
    return CrawlResult(
        payload=payload,
        duration_sec=duration_sec,
        html=html,
        screenshot_png=screenshot_png,
    )
