"""Tests for crawl job consumer."""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from mfa.db.models import CrawlJob, ScoreJob, Url
from mfa.schemas.signals import SignalFeatures, SignalSnapshotPayload
from sqlalchemy import select

from mfa_crawler.artifacts import DOM_METRICS_FILENAME, HTML_FILENAME, SCREENSHOT_FILENAME
from mfa_crawler.consumer import poll_and_process_once, process_claimed_job
from mfa_crawler.errors import CrawlNotFoundError, CrawlTimeoutError
from mfa_crawler.persist import PersistedSnapshot

pytestmark = pytest.mark.skipif(
    os.getenv("MFA_RUN_INTEGRATION") != "1",
    reason="Set MFA_RUN_INTEGRATION=1 with Postgres running to execute integration tests",
)


def _persisted_snapshot(url_id: uuid.UUID, artifact_dir: Path | None = None) -> PersistedSnapshot:
    return PersistedSnapshot(
        snapshot_id=uuid.uuid4(),
        url_id=url_id,
        version=1,
        evidence_hash="a" * 64,
        persona="direct",
        crawl_duration_sec=1.2,
        payload=SignalSnapshotPayload(
            crawl_ts=datetime(2026, 7, 6, 12, 0, 0, tzinfo=UTC),
            features=SignalFeatures(content_word_count=10),
        ),
        artifact_dir=artifact_dir,
    )


async def _seed_queued_job(session_factory) -> tuple[uuid.UUID, uuid.UUID]:
    url_id = uuid.uuid4()
    job_id = uuid.uuid4()
    async with session_factory() as session:
        session.add(
            Url(
                id=url_id,
                url="https://example.com",
                normalized_url="https://example.com",
                url_hash=f"hash-{url_id.hex[:12]}",
                domain="example.com",
            )
        )
        session.add(
            CrawlJob(
                id=job_id,
                url_id=url_id,
                status="queued",
                priority=0,
                idempotency_key=f"key-{job_id.hex[:12]}",
            )
        )
        await session.commit()
    return job_id, url_id


# ---------------------------------------------------------------------------
# Success path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_process_claimed_job_marks_completed(session_factory) -> None:
    job_id, url_id = await _seed_queued_job(session_factory)
    snapshot = _persisted_snapshot(url_id)
    mock_persist = AsyncMock(return_value=snapshot)

    async with session_factory() as session:
        from mfa.db.models import SignalSnapshot

        session.add(
            SignalSnapshot(
                id=snapshot.snapshot_id,
                url_id=url_id,
                version=snapshot.version,
                signals=snapshot.payload.to_db(),
                evidence_hash=snapshot.evidence_hash,
                persona=snapshot.persona,
                crawl_duration_sec=snapshot.crawl_duration_sec,
            )
        )
        await session.commit()

    with patch("mfa_crawler.consumer.crawl_and_persist", mock_persist):
        await process_claimed_job(job_id, url_id, session_factory=session_factory)

    async with session_factory() as session:
        job = await session.scalar(select(CrawlJob).where(CrawlJob.id == job_id))
        assert job is not None
        assert job.status == "completed"
        assert job.crawl_error_type is None

        score_job = await session.scalar(
            select(ScoreJob).where(ScoreJob.signal_snapshot_id == snapshot.snapshot_id)
        )
        assert score_job is not None
        assert score_job.status == "queued"
        assert score_job.url_id == url_id


# ---------------------------------------------------------------------------
# Permanent failure path (CrawlNotFoundError)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_process_claimed_job_permanent_failure_marks_error_type(session_factory) -> None:
    """CrawlNotFoundError → status=failed, crawl_error_type=not_found, no re-raise."""
    job_id, url_id = await _seed_queued_job(session_factory)
    mock_persist = AsyncMock(side_effect=CrawlNotFoundError("https://example.com/gone"))

    with patch("mfa_crawler.consumer.crawl_and_persist", mock_persist):
        # Must NOT raise — permanent failures are expected outcomes.
        await process_claimed_job(job_id, url_id, session_factory=session_factory)

    async with session_factory() as session:
        job = await session.scalar(select(CrawlJob).where(CrawlJob.id == job_id))
        assert job is not None
        assert job.status == "failed"
        assert job.crawl_error_type == "not_found"
        assert "not found" in (job.error_message or "").lower()


# ---------------------------------------------------------------------------
# Transient failure path (CrawlTimeoutError)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_process_claimed_job_transient_failure_reraises(session_factory) -> None:
    """CrawlTimeoutError → status=failed, crawl_error_type=timeout, exception re-raised."""
    job_id, url_id = await _seed_queued_job(session_factory)
    mock_persist = AsyncMock(
        side_effect=CrawlTimeoutError("page load timed out for 'https://example.com'")
    )

    with patch("mfa_crawler.consumer.crawl_and_persist", mock_persist):
        with pytest.raises(CrawlTimeoutError):
            await process_claimed_job(job_id, url_id, session_factory=session_factory)

    async with session_factory() as session:
        job = await session.scalar(select(CrawlJob).where(CrawlJob.id == job_id))
        assert job is not None
        assert job.status == "failed"
        assert job.crawl_error_type == "timeout"


# ---------------------------------------------------------------------------
# Unknown / unexpected error
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_process_claimed_job_marks_failed_on_unknown_error(session_factory) -> None:
    """Non-CrawlError exceptions → status=failed, no crawl_error_type, re-raised."""
    job_id, url_id = await _seed_queued_job(session_factory)
    mock_persist = AsyncMock(side_effect=RuntimeError("unexpected"))

    with patch("mfa_crawler.consumer.crawl_and_persist", mock_persist):
        with pytest.raises(RuntimeError, match="unexpected"):
            await process_claimed_job(job_id, url_id, session_factory=session_factory)

    async with session_factory() as session:
        job = await session.scalar(select(CrawlJob).where(CrawlJob.id == job_id))
        assert job is not None
        assert job.status == "failed"
        assert job.crawl_error_type is None


# ---------------------------------------------------------------------------
# Poll loop
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_poll_and_process_once_no_jobs(session_factory) -> None:
    processed = await poll_and_process_once(session_factory=session_factory)
    assert processed is False


@pytest.mark.asyncio
@pytest.mark.integration
async def test_poll_and_process_once_end_to_end(
    session_factory, tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("EVIDENCE_DIR", str(tmp_path))
    job_id, url_id = await _seed_queued_job(session_factory)

    processed = await poll_and_process_once(session_factory=session_factory)
    assert processed is True

    async with session_factory() as session:
        job = await session.scalar(select(CrawlJob).where(CrawlJob.id == job_id))
        assert job is not None
        assert job.status == "completed"

    artifact_dir = tmp_path / str(url_id) / "1"
    assert (artifact_dir / HTML_FILENAME).exists()
    assert (artifact_dir / SCREENSHOT_FILENAME).exists()
    assert (artifact_dir / DOM_METRICS_FILENAME).exists()
