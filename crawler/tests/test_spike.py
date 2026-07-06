"""Tests for crawler spike data loading and report aggregation."""

from __future__ import annotations

from mfa_crawler.spike import (
    SpikeCrawlFailure,
    SpikeCrawlSuccess,
    build_spike_report,
    render_spike_report_markdown,
)
from mfa_crawler.spike_data import SpikeTarget, list_urls_for_domain, load_spike_targets


def test_load_spike_targets_returns_one_per_domain() -> None:
    targets = load_spike_targets(domain_limit=5)
    assert len(targets) == 5
    domains = {target.domain for target in targets}
    assert len(domains) == 5
    assert all(target.url.startswith("https://") for target in targets)


def test_list_urls_for_domain_prefers_article() -> None:
    records = [
        {"domain": "example.com", "url": "https://example.com/", "page_type": "homepage"},
        {"domain": "example.com", "url": "https://example.com/story", "page_type": "article"},
    ]
    assert list_urls_for_domain(records, "example.com")[0] == "https://example.com/story"


def test_build_spike_report_aggregates_metrics() -> None:
    targets = [
        SpikeTarget(
            domain="a.com",
            candidate_urls=("https://a.com/",),
            primary_gold_label="MFA_High",
            content_category="news",
            label_source="test",
        ),
        SpikeTarget(
            domain="b.com",
            candidate_urls=("https://b.com/",),
            primary_gold_label="Non_MFA",
            content_category="news",
            label_source="test",
        ),
    ]
    successes = [
        SpikeCrawlSuccess(
            target=targets[0],
            url="https://a.com/",
            duration_sec=2.0,
            metrics={
                "ad_slots_count": 5,
                "ad_to_content_ratio": 0.4,
                "content_word_count": 100,
            },
        ),
        SpikeCrawlSuccess(
            target=targets[1],
            url="https://b.com/",
            duration_sec=4.0,
            metrics={
                "ad_slots_count": 1,
                "ad_to_content_ratio": 0.1,
                "content_word_count": 500,
            },
        ),
    ]
    failures = [
        SpikeCrawlFailure(target=targets[1], error="timeout"),
    ]

    report = build_spike_report(
        targets=targets,
        successes=successes[:1],
        failures=failures,
        delay_sec=1.0,
    )

    assert report["attempted"] == 2
    assert report["succeeded"] == 1
    assert report["failed"] == 1
    assert report["success_rate"] == 0.5
    assert report["crawl_duration_sec"]["median"] == 2.0
    assert report["metrics"]["ad_slots_count"]["median"] == 5.0
    assert "MFA_High" in report["by_primary_gold_label"]
    assert len(report["top_metrics_by_median"]) >= 1

    markdown = render_spike_report_markdown(report)
    assert "Crawler spike report" in markdown
    assert "ad_slots_count" in markdown
