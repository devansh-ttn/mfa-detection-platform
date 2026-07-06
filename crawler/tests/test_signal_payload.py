"""Unit tests for DOM metric mapping."""

from datetime import UTC, datetime

from mfa.schemas.signals import SIGNAL_SCHEMA_VERSION, SignalFeatures, SignalSnapshotPayload


def test_signal_features_from_dom_dict() -> None:
    features = SignalFeatures(
        ad_slots_count=3,
        ads_above_fold=2,
        sticky_ad_count=1,
        ad_to_content_ratio=0.25,
        content_word_count=120,
    )
    assert features.refresh_events_60s is None
    assert features.iframe_ad_count is None


def test_dom_metrics_to_snapshot_payload() -> None:
    crawl_ts = datetime(2026, 7, 6, 12, 0, 0, tzinfo=UTC)
    features = SignalFeatures(
        ad_slots_count=0,
        ads_above_fold=0,
        sticky_ad_count=0,
        ad_to_content_ratio=0.0,
        content_word_count=42,
    )
    payload = SignalSnapshotPayload(crawl_ts=crawl_ts, features=features)
    doc = payload.to_db()

    assert doc["schema_version"] == SIGNAL_SCHEMA_VERSION
    assert doc["ad_slots_count"] == 0
    assert doc["content_word_count"] == 42
    assert doc["refresh_events_60s"] is None
    assert "features" not in doc

    restored = SignalSnapshotPayload.from_db(doc)
    assert restored == payload
