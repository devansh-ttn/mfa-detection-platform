"""Unit tests for dom_parser metric keys."""

from mfa.schemas.signals import CRAWL_FEATURE_NAMES

from mfa_crawler.dom_parser import CORE_DOM_METRIC_NAMES, DOM_METRIC_NAMES, EXTENDED_DOM_METRIC_NAMES


def test_core_dom_metrics_are_crawl_feature_names() -> None:
    for name in CORE_DOM_METRIC_NAMES:
        assert name in CRAWL_FEATURE_NAMES


def test_extended_dom_metrics_are_crawl_feature_names() -> None:
    for name in EXTENDED_DOM_METRIC_NAMES:
        assert name in CRAWL_FEATURE_NAMES


def test_extract_dom_metrics_js_returns_expected_keys() -> None:
    from mfa_crawler.dom_parser import _EXTRACT_DOM_METRICS_JS

    for name in DOM_METRIC_NAMES:
        assert name in _EXTRACT_DOM_METRICS_JS


def test_dom_metric_names_cover_core_and_extended() -> None:
    assert DOM_METRIC_NAMES == CORE_DOM_METRIC_NAMES + EXTENDED_DOM_METRIC_NAMES
