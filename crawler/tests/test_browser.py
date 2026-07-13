"""Unit tests for browser persona and referrer configuration."""

from __future__ import annotations

import os

import pytest

from mfa_crawler.browser import REFERRER_SOURCES, resolve_referrer_url
from mfa_crawler.errors import (
    CrawlInvalidUrlError,
    CrawlUnreachableError,
    classify_playwright_goto_error,
)


def test_resolve_referrer_url_direct_returns_none() -> None:
    assert resolve_referrer_url("direct") is None


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("outbrain", REFERRER_SOURCES["outbrain"]),
        ("taboola", REFERRER_SOURCES["taboola"]),
    ],
)
def test_resolve_referrer_url_referral(monkeypatch: pytest.MonkeyPatch, source: str, expected: str) -> None:
    monkeypatch.setenv("CRAWL_REFERRER_SOURCE", source)
    assert resolve_referrer_url("referral") == expected


def test_resolve_referrer_url_defaults_to_outbrain(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CRAWL_REFERRER_SOURCE", raising=False)
    assert resolve_referrer_url("referral") == REFERRER_SOURCES["outbrain"]


def test_resolve_referrer_url_unknown_source_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CRAWL_REFERRER_SOURCE", "unknown-network")
    with pytest.raises(ValueError, match="unsupported CRAWL_REFERRER_SOURCE"):
        resolve_referrer_url("referral")


def test_resolve_referrer_url_unknown_persona_raises() -> None:
    with pytest.raises(ValueError, match="unsupported persona"):
        resolve_referrer_url("bot")


def test_classify_playwright_goto_error_dns_is_unreachable() -> None:
    exc = RuntimeError(
        "Page.goto: net::ERR_NAME_NOT_RESOLVED at https://bonvoyaged.com/"
    )
    classified = classify_playwright_goto_error(exc, "https://bonvoyaged.com/")
    assert isinstance(classified, CrawlUnreachableError)
    assert classified.error_type == "unreachable"


def test_classify_playwright_goto_error_invalid_url() -> None:
    exc = RuntimeError("Page.goto: net::ERR_INVALID_URL at foo")
    classified = classify_playwright_goto_error(exc, "foo")
    assert isinstance(classified, CrawlInvalidUrlError)


def test_classify_playwright_goto_error_unknown_passthrough() -> None:
    exc = RuntimeError("Page.evaluate: execution context was destroyed")
    assert classify_playwright_goto_error(exc, "https://example.com/") is exc
