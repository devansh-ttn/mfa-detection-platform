"""Playwright browser lifecycle for single-page crawl."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

import structlog
from playwright.async_api import Browser, Page, Playwright, async_playwright

logger = structlog.get_logger(__name__)

DEFAULT_USER_AGENT = (
    "MFA-Detection-Crawler/0.1 (+https://github.com/ttn/mfa-detection-platform; research)"
)


@dataclass(frozen=True)
class CrawlSettings:
    timeout_ms: int = 30_000
    user_agent: str = DEFAULT_USER_AGENT
    headless: bool = True


def load_crawl_settings() -> CrawlSettings:
    headless_raw = os.getenv("CRAWL_HEADLESS", "true").lower()
    headless = headless_raw not in {"0", "false", "no"}
    timeout_ms = int(os.getenv("CRAWL_TIMEOUT_MS", "30000"))
    user_agent = os.getenv("CRAWL_USER_AGENT", DEFAULT_USER_AGENT)
    return CrawlSettings(timeout_ms=timeout_ms, user_agent=user_agent, headless=headless)


@asynccontextmanager
async def crawl_page(
    url: str,
    *,
    settings: CrawlSettings | None = None,
    persona: str = "direct",
) -> AsyncIterator[Page]:
    """Launch Chromium, navigate to *url*, yield the page, then tear down."""
    if persona != "direct":
        # TODO(MVP): referral persona with Outbrain/Taboola referrer header
        raise ValueError(f"unsupported persona: {persona}")

    cfg = settings or load_crawl_settings()
    playwright: Playwright | None = None
    browser: Browser | None = None

    try:
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(headless=cfg.headless)
        context = await browser.new_context(user_agent=cfg.user_agent)
        page = await context.new_page()
        page.set_default_timeout(cfg.timeout_ms)

        logger.info("crawl_navigate_start", url=url, persona=persona)
        response = await page.goto(url, wait_until="domcontentloaded")
        if response is None or not response.ok:
            status = response.status if response else None
            raise RuntimeError(f"navigation failed for {url!r} (status={status})")

        logger.info("crawl_navigate_done", url=url, status=response.status)
        yield page
        await context.close()
    except Exception:
        logger.exception("crawl_page_error", url=url)
        raise
    finally:
        if browser is not None:
            await browser.close()
        if playwright is not None:
            await playwright.stop()
