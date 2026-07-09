"""Typed crawl exception hierarchy.

Every exception carries an ``error_type`` class attribute that the consumer
uses to decide whether to retry or permanently skip the URL.

Permanent types (``PERMANENT_ERROR_TYPES``) are written to
``crawl_jobs.crawl_error_type`` and cause ``claim_next_crawl_job`` to skip
any future queued job for the same URL that was created before the failure
was recorded — preventing wasteful re-crawls of definitively broken URLs.

A re-submission via the ingestion API after a permanent failure creates a new
``crawl_jobs`` row with a newer ``created_at``, which clears the skip condition
and triggers a fresh crawl attempt ("re-try after URL changed" semantics).
"""

from __future__ import annotations

from typing import Literal

CrawlErrorType = Literal[
    "transient",       # Network hiccup or unknown error; eligible for retry
    "not_found",       # HTTP 404 / 410 — page definitively does not exist
    "http_error",      # Other non-2xx HTTP status (4xx/5xx)
    "timeout",         # Page load exceeded configured timeout_ms
    "robots_denied",   # robots.txt disallows this URL  — TODO(MVP)
    "invalid_url",     # Malformed or protocol-unsupported URL
]

# Error types that will never self-resolve; no automatic retry.
PERMANENT_ERROR_TYPES: frozenset[str] = frozenset({
    "not_found",
    "invalid_url",
    "robots_denied",
})


class CrawlError(RuntimeError):
    """Base class for all crawl exceptions.

    Subclasses override ``error_type`` as a class variable so callers can
    inspect ``exc.error_type`` without isinstance checks.
    """

    error_type: CrawlErrorType = "transient"


class CrawlNavigationError(CrawlError):
    """Non-2xx HTTP response from the target page.

    Carries the raw ``http_status`` for logging.
    """

    error_type: CrawlErrorType = "http_error"

    def __init__(self, url: str, http_status: int | None) -> None:
        self.http_status = http_status
        super().__init__(f"HTTP {http_status} navigating {url!r}")


class CrawlNotFoundError(CrawlNavigationError):
    """HTTP 404 or 410 — URL definitively does not exist.

    Treated as a permanent failure; the URL will not be re-crawled unless
    explicitly re-submitted via the ingestion API.
    """

    error_type: CrawlErrorType = "not_found"

    def __init__(self, url: str, http_status: int = 404) -> None:
        self.http_status = http_status
        # Bypass CrawlNavigationError.__init__ to set a cleaner message.
        RuntimeError.__init__(self, f"HTTP {http_status} — page not found: {url!r}")


class CrawlTimeoutError(CrawlError):
    """Page load timed out (Playwright TimeoutError)."""

    error_type: CrawlErrorType = "timeout"


class CrawlInvalidUrlError(CrawlError):
    """Malformed URL or unsupported protocol.

    Treated as a permanent failure; no retry makes sense.
    """

    error_type: CrawlErrorType = "invalid_url"
