"""Tests for crawl job consumer."""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from mfa.db.models import CrawlJob, Url
from mfa.schemas.signals import SignalFeatures, SignalSnapshotPayload
from sqlalchemy import select

from mfa_crawler.artifacts import DOM_METRICS_FILENAME, HTML_FILENAME, SCREENSHOT_FILENAME
from mfa_crawler.consumer import poll_and_process_once, process_claimed_job
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


@pytest.mark.asyncio
async def test_process_claimed_job_marks_completed(session_factory) -> None:
    job_id, url_id = await _seed_queued_job(session_factory)
    mock_persist = AsyncMock(return_value=_persisted_snapshot(url_id))

    with patch("mfa_crawler.consumer.crawl_and_persist", mock_persist):
        await process_claimed_job(job_id, url_id, session_factory=session_factory)

    async with session_factory() as session:
        job = await session.scalar(select(CrawlJob).where(CrawlJob.id == job_id))
        assert job is not None
        assert job.status == "completed"


@pytest.mark.asyncio
async def test_process_claimed_job_marks_failed_on_error(session_factory) -> None:
    job_id, url_id = await _seed_queued_job(session_factory)
    mock_persist = AsyncMock(side_effect=RuntimeError("crawl failed"))

    with patch("mfa_crawler.consumer.crawl_and_persist", mock_persist):
        with pytest.raises(RuntimeError, match="crawl failed"):
            await process_claimed_job(job_id, url_id, session_factory=session_factory)

    async with session_factory() as session:
        job = await session.scalar(select(CrawlJob).where(CrawlJob.id == job_id))
        assert job is not None
        assert job.status == "failed"
        assert job.error_message == "crawl failed"


@pytest.mark.asyncio
async def test_poll_and_process_once_no_jobs(session_factory) -> None:
    processed = await poll_and_process_once(session_factory=session_factory)
    assert processed is False


@pytest.mark.asyncio
@pytest.mark.integration
async def test_poll_and_process_once_end_to_end(session_factory, tmp_path: Path, monkeypatch) -> None:
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
