"""Unit tests for dom_parser metric keys."""

from mfa.schemas.signals import CRAWL_FEATURE_NAMES

# Core metrics populated by dom_parser in POC-2.2
CORE_DOM_METRICS = (
    "ad_to_content_ratio",
    "ads_above_fold",
    "ad_slots_count",
    "sticky_ad_count",
    "content_word_count",
)


def test_core_dom_metrics_are_crawl_feature_names() -> None:
    for name in CORE_DOM_METRICS:
        assert name in CRAWL_FEATURE_NAMES


def test_extract_dom_metrics_js_returns_expected_keys() -> None:
    from mfa_crawler.dom_parser import _EXTRACT_DOM_METRICS_JS

    assert "ad_slots_count" in _EXTRACT_DOM_METRICS_JS
    assert "ads_above_fold" in _EXTRACT_DOM_METRICS_JS
    assert "sticky_ad_count" in _EXTRACT_DOM_METRICS_JS
    assert "ad_to_content_ratio" in _EXTRACT_DOM_METRICS_JS
    assert "content_word_count" in _EXTRACT_DOM_METRICS_JS
