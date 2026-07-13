"""Tests for signal_snapshots persistence."""

from __future__ import annotations

import os
import uuid

import pytest
from datetime import UTC, datetime
from pathlib import Path

import pytest
from mfa.db.models import SignalSnapshot
from mfa.schemas.signals import SignalFeatures, SignalSnapshotPayload, compute_evidence_hash
from sqlalchemy import select

from mfa_crawler.persist import crawl_and_persist, next_snapshot_version, persist_signal_snapshot

pytestmark = pytest.mark.skipif(
    os.getenv("MFA_RUN_INTEGRATION") != "1",
    reason="Set MFA_RUN_INTEGRATION=1 with Postgres running to execute integration tests",
)


def _sample_payload() -> SignalSnapshotPayload:
    return SignalSnapshotPayload(
        crawl_ts=datetime(2026, 7, 6, 12, 0, 0, tzinfo=UTC),
        features=SignalFeatures(
            ad_to_content_ratio=0.15,
            ad_slots_count=2,
            content_word_count=80,
        ),
    )


@pytest.mark.asyncio
async def test_next_snapshot_version_starts_at_one(session_factory, seed_url) -> None:
    url_id = await seed_url()
    async with session_factory() as session:
        assert await next_snapshot_version(session, url_id) == 1


@pytest.mark.asyncio
async def test_persist_signal_snapshot_writes_row(session_factory, seed_url) -> None:
    url_id = await seed_url()
    payload = _sample_payload()
    signals = payload.to_db()

    async with session_factory() as session:
        result = await persist_signal_snapshot(
            session,
            url_id=url_id,
            payload=payload,
            crawl_duration_sec=2.5,
            persona="direct",
        )
        await session.commit()

    assert result.version == 1
    assert result.persona == "direct"
    assert result.evidence_hash == compute_evidence_hash(signals)

    async with session_factory() as session:
        row = await session.scalar(
            select(SignalSnapshot).where(SignalSnapshot.id == result.snapshot_id)
        )
        assert row is not None
        assert row.signals == signals
        assert row.crawl_duration_sec == 2.5


@pytest.mark.asyncio
async def test_persist_signal_snapshot_increments_version(session_factory, seed_url) -> None:
    url_id = await seed_url()
    payload = _sample_payload()

    async with session_factory() as session:
        first = await persist_signal_snapshot(
            session,
            url_id=url_id,
            payload=payload,
            crawl_duration_sec=1.0,
        )
        second = await persist_signal_snapshot(
            session,
            url_id=url_id,
            payload=payload,
            crawl_duration_sec=1.5,
        )
        await session.commit()

    assert first.version == 1
    assert second.version == 2


@pytest.mark.asyncio
async def test_persist_signal_snapshot_merges_enrichment(session_factory, seed_url) -> None:
    url_id = await seed_url()
    payload = _sample_payload()

    async with session_factory() as session:
        result = await persist_signal_snapshot(
            session,
            url_id=url_id,
            payload=payload,
            crawl_duration_sec=2.5,
            persona="direct",
            enrichment={"referral_direct_delta_score": 0.42},
        )
        await session.commit()

    assert result.evidence_hash == compute_evidence_hash(
        {**payload.to_db(), "referral_direct_delta_score": 0.42}
    )

    async with session_factory() as session:
        row = await session.scalar(
            select(SignalSnapshot).where(SignalSnapshot.id == result.snapshot_id)
        )
        assert row is not None
        assert row.signals["referral_direct_delta_score"] == 0.42


@pytest.mark.asyncio
async def test_persist_signal_snapshot_unknown_url_raises(session_factory) -> None:
    payload = _sample_payload()
    async with session_factory() as session:
        with pytest.raises(LookupError, match="url_id not found"):
            await persist_signal_snapshot(
                session,
                url_id=uuid.uuid4(),
                payload=payload,
                crawl_duration_sec=1.0,
            )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_crawl_and_persist_integration(session_factory, seed_url, tmp_path: Path) -> None:
    url_id = await seed_url(url="https://example.com")

    result = await crawl_and_persist(
        url_id,
        session_factory=session_factory,
        evidence_base_dir=tmp_path,
    )

    assert result.version == 1
    assert result.persona == "direct"
    assert len(result.evidence_hash) == 64
    assert result.payload.to_db()["schema_version"] == "v1"
    assert result.artifact_dir is not None
    assert (result.artifact_dir / "page.html").exists()
    assert (result.artifact_dir / "screenshot.png").exists()
    assert (result.artifact_dir / "dom_metrics.json").exists()
