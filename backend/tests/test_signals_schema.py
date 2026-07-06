"""Unit tests for signal snapshot Pydantic schema."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from mfa.schemas.signals import (
    CRAWL_FEATURE_NAMES,
    SIGNAL_SCHEMA_VERSION,
    SignalFeatures,
    SignalSnapshotPayload,
    compute_evidence_hash,
)


def _sample_features() -> SignalFeatures:
    return SignalFeatures(
        ad_to_content_ratio=0.42,
        ads_above_fold=3,
        ad_slots_count=8,
        sticky_ad_count=2,
        content_word_count=450,
        refresh_events_60s=0,
        author_page_exists=False,
        slideshow_pagination_depth=1,
    )


def test_crawl_feature_names_count() -> None:
    assert len(CRAWL_FEATURE_NAMES) == 16


def test_signal_snapshot_payload_round_trip() -> None:
    crawl_ts = datetime(2026, 7, 6, 12, 0, 0, tzinfo=UTC)
    payload = SignalSnapshotPayload(crawl_ts=crawl_ts, features=_sample_features())

    db_doc = payload.to_db()
    assert db_doc["schema_version"] == SIGNAL_SCHEMA_VERSION
    assert db_doc["crawl_ts"] == crawl_ts.isoformat().replace("+00:00", "Z")
    assert db_doc["ad_to_content_ratio"] == 0.42
    assert "features" not in db_doc

    restored = SignalSnapshotPayload.from_db(db_doc)
    assert restored == payload


def test_signal_snapshot_reads_legacy_schema_version() -> None:
    crawl_ts = datetime(2026, 7, 6, 12, 0, 0, tzinfo=UTC)
    db_doc = SignalSnapshotPayload(crawl_ts=crawl_ts, features=_sample_features()).to_db()
    db_doc["schema_version"] = "poc-v1"

    restored = SignalSnapshotPayload.from_db(db_doc)
    assert restored.schema_version == SIGNAL_SCHEMA_VERSION


def test_signal_snapshot_ignores_enrichment_fields_in_db() -> None:
    crawl_ts = datetime(2026, 7, 6, 12, 0, 0, tzinfo=UTC)
    db_doc = SignalSnapshotPayload(
        crawl_ts=crawl_ts,
        features=_sample_features(),
    ).to_db()
    db_doc["paid_traffic_pct"] = 90.0

    restored = SignalSnapshotPayload.from_db(db_doc)
    assert "paid_traffic_pct" not in restored.to_db()


def test_signal_snapshot_rejects_invalid_ratio() -> None:
    with pytest.raises(ValidationError):
        SignalFeatures(ad_to_content_ratio=1.5)


def test_signal_snapshot_rejects_unsupported_schema_version() -> None:
    crawl_ts = datetime(2026, 7, 6, 12, 0, 0, tzinfo=UTC)
    with pytest.raises(ValidationError):
        SignalSnapshotPayload(
            schema_version="v99",
            crawl_ts=crawl_ts,
            features=_sample_features(),
        )


def test_compute_evidence_hash_is_stable() -> None:
    crawl_ts = datetime(2026, 7, 6, 12, 0, 0, tzinfo=UTC)
    doc = SignalSnapshotPayload(crawl_ts=crawl_ts, features=_sample_features()).to_db()
    first = compute_evidence_hash(doc)
    second = compute_evidence_hash(doc)
    assert first == second
    assert len(first) == 64
