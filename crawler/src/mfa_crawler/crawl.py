"""Crawl orchestration with dwell, refresh detection, and dual-persona merge."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from mfa.schemas.signals import CRAWL_FEATURE_NAMES, SignalFeatures, SignalSnapshotPayload

from mfa_crawler.browser import crawl_page, load_crawl_settings
from mfa_crawler.dom_parser import extract_dom_metrics
from mfa_crawler.refresh import observe_refresh_events

# Numeric crawl features compared when computing referral-direct delta.
_DELTA_FEATURE_NAMES: tuple[str, ...] = tuple(
    name
    for name in CRAWL_FEATURE_NAMES
    if name
    not in {
        "author_page_exists",
        "refresh_events_60s",
        "avg_refresh_interval_sec",
    }
)


@dataclass(frozen=True)
class CrawlResult:
    payload: SignalSnapshotPayload
    duration_sec: float
    html: str
    screenshot_png: bytes
    enrichment: dict[str, Any] = field(default_factory=dict)


def load_dwell_sec() -> float:
    """Return dwell seconds from env (0 for fast tests, 60 for production)."""
    return float(os.getenv("CRAWL_DWELL_SEC", "0"))


def load_dual_persona_enabled() -> bool:
    raw = os.getenv("CRAWL_DUAL_PERSONA", "false").lower()
    return raw in {"1", "true", "yes"}


def compute_referral_direct_delta_score(
    direct: SignalFeatures,
    referral: SignalFeatures,
) -> float:
    """Mean absolute delta across comparable numeric crawl features."""
    deltas: list[float] = []
    for name in _DELTA_FEATURE_NAMES:
        direct_val = getattr(direct, name)
        referral_val = getattr(referral, name)
        if direct_val is None or referral_val is None:
            continue
        if isinstance(direct_val, bool):
            deltas.append(1.0 if direct_val != referral_val else 0.0)
        else:
            deltas.append(abs(float(direct_val) - float(referral_val)))
    if not deltas:
        return 0.0
    return sum(deltas) / len(deltas)


def merge_persona_features(direct: SignalFeatures, referral: SignalFeatures) -> SignalFeatures:
    """Merge dual-persona features; direct values win, referral fills nulls."""
    merged: dict[str, Any] = direct.model_dump()
    referral_data = referral.model_dump()
    for key, referral_val in referral_data.items():
        if merged.get(key) is None and referral_val is not None:
            merged[key] = referral_val
    return SignalFeatures.model_validate(merged)


async def _crawl_single_persona(
    url: str,
    *,
    persona: str,
    dwell_sec: float,
) -> CrawlResult:
    settings = load_crawl_settings()
    started = time.perf_counter()

    async with crawl_page(url, settings=settings, persona=persona) as page:
        features = await extract_dom_metrics(page)
        refresh_events, avg_interval = await observe_refresh_events(page, dwell_sec)
        features = features.model_copy(
            update={
                "refresh_events_60s": refresh_events,
                "avg_refresh_interval_sec": avg_interval,
            }
        )
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


async def crawl_url(
    url: str,
    *,
    persona: str = "direct",
    dwell_sec: float | None = None,
    dual_persona: bool | None = None,
) -> CrawlResult:
    """Navigate, extract DOM metrics, optional dwell/refresh, return validated result."""
    resolved_dwell = load_dwell_sec() if dwell_sec is None else dwell_sec
    run_dual = load_dual_persona_enabled() if dual_persona is None else dual_persona

    if not run_dual:
        return await _crawl_single_persona(url, persona=persona, dwell_sec=resolved_dwell)

    direct_result = await _crawl_single_persona(url, persona="direct", dwell_sec=resolved_dwell)
    referral_result = await _crawl_single_persona(url, persona="referral", dwell_sec=resolved_dwell)

    merged_features = merge_persona_features(
        direct_result.payload.features,
        referral_result.payload.features,
    )
    delta_score = compute_referral_direct_delta_score(
        direct_result.payload.features,
        referral_result.payload.features,
    )

    merged_payload = SignalSnapshotPayload(
        crawl_ts=direct_result.payload.crawl_ts,
        features=merged_features,
    )
    return CrawlResult(
        payload=merged_payload,
        duration_sec=direct_result.duration_sec + referral_result.duration_sec,
        html=direct_result.html,
        screenshot_png=direct_result.screenshot_png,
        enrichment={"referral_direct_delta_score": delta_score},
    )
