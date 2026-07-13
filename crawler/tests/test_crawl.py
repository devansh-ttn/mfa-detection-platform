"""Unit tests for dual-persona crawl orchestration."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from mfa.schemas.signals import SignalFeatures, SignalSnapshotPayload

from mfa_crawler.crawl import (
    compute_referral_direct_delta_score,
    load_dual_persona_enabled,
    load_dwell_sec,
    merge_persona_features,
)


def test_load_dwell_sec_default_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CRAWL_DWELL_SEC", raising=False)
    assert load_dwell_sec() == 0.0


def test_load_dwell_sec_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CRAWL_DWELL_SEC", "60")
    assert load_dwell_sec() == 60.0


def test_load_dual_persona_disabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CRAWL_DUAL_PERSONA", raising=False)
    assert load_dual_persona_enabled() is False


def test_load_dual_persona_enabled_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CRAWL_DUAL_PERSONA", "true")
    assert load_dual_persona_enabled() is True


def test_merge_persona_features_direct_wins_non_null() -> None:
    direct = SignalFeatures(ad_slots_count=3, content_word_count=100)
    referral = SignalFeatures(ad_slots_count=5, native_ad_count=2)
    merged = merge_persona_features(direct, referral)
    assert merged.ad_slots_count == 3
    assert merged.native_ad_count == 2


def test_compute_referral_direct_delta_score() -> None:
    direct = SignalFeatures(ad_to_content_ratio=0.2, ad_slots_count=2)
    referral = SignalFeatures(ad_to_content_ratio=0.5, ad_slots_count=4)
    delta = compute_referral_direct_delta_score(direct, referral)
    assert delta == pytest.approx(1.15)


@pytest.mark.asyncio
async def test_crawl_url_dual_persona_adds_delta_enrichment() -> None:
    from mfa_crawler.crawl import CrawlResult, crawl_url

    direct_features = SignalFeatures(ad_slots_count=2, ad_to_content_ratio=0.1)
    referral_features = SignalFeatures(ad_slots_count=4, ad_to_content_ratio=0.3)
    crawl_ts = datetime(2026, 7, 10, 12, 0, 0, tzinfo=UTC)

    direct_result = CrawlResult(
        payload=SignalSnapshotPayload(crawl_ts=crawl_ts, features=direct_features),
        duration_sec=1.0,
        html="<html>direct</html>",
        screenshot_png=b"png-direct",
    )
    referral_result = CrawlResult(
        payload=SignalSnapshotPayload(crawl_ts=crawl_ts, features=referral_features),
        duration_sec=1.2,
        html="<html>referral</html>",
        screenshot_png=b"png-referral",
    )

    with patch(
        "mfa_crawler.crawl._crawl_single_persona",
        new=AsyncMock(side_effect=[direct_result, referral_result]),
    ):
        result = await crawl_url("https://example.com/article", dual_persona=True, dwell_sec=0)

    assert result.enrichment["referral_direct_delta_score"] == pytest.approx(1.1)
    assert result.payload.features.ad_slots_count == 2
    assert result.duration_sec == pytest.approx(2.2)
    assert result.html == "<html>direct</html>"
