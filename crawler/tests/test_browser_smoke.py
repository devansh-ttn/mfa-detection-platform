"""Integration smoke test — requires Playwright browsers."""

from __future__ import annotations

import os

import pytest
from mfa.schemas.signals import SIGNAL_SCHEMA_VERSION

pytestmark = pytest.mark.integration


@pytest.mark.skipif(
    os.getenv("PLAYWRIGHT_SMOKE") != "1",
    reason="set PLAYWRIGHT_SMOKE=1 to run browser integration tests",
)
@pytest.mark.asyncio
async def test_crawl_example_com() -> None:
    from mfa_crawler.crawl import crawl_url

    result = await crawl_url("https://example.com")
    payload = result.payload
    duration_sec = result.duration_sec
    doc = payload.to_db()

    assert doc["schema_version"] == SIGNAL_SCHEMA_VERSION
    assert doc["content_word_count"] is not None
    assert doc["content_word_count"] > 0
    assert duration_sec > 0
