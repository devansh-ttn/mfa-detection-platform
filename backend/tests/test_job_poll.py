"""Tests for Postgres-backed crawl job polling."""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from mfa.db.models import Base, CrawlJob, SignalSnapshot, Url
from mfa.ingestion.job_poll import claim_next_crawl_job, mark_job_completed, mark_job_failed

pytestmark = pytest.mark.skipif(
    os.getenv("MFA_RUN_INTEGRATION") != "1",
    reason="Set MFA_RUN_INTEGRATION=1 with Postgres running to execute integration tests",
)


@pytest.fixture
async def test_engine():
    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://mfa:mfa@localhost:5432/mfa",
    )
    engine = create_async_engine(database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def session_factory(test_engine):
    return async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


async def _seed_job(
    session_factory,
    *,
    status: str = "queued",
    priority: int = 0,
    crawl_error_type: str | None = None,
    url_id: uuid.UUID | None = None,
    created_at: datetime | None = None,
) -> CrawlJob:
    _url_id = url_id or uuid.uuid4()
    job_id = uuid.uuid4()
    async with session_factory() as session:
        if url_id is None:
            session.add(
                Url(
                    id=_url_id,
                    url="https://example.com/article",
                    normalized_url="https://example.com/article",
                    url_hash=f"hash-{_url_id.hex[:12]}",
                    domain="example.com",
                )
            )
        kwargs: dict = dict(
            id=job_id,
            url_id=_url_id,
            status=status,
            priority=priority,
            crawl_error_type=crawl_error_type,
            idempotency_key=f"key-{job_id.hex[:12]}",
        )
        if created_at is not None:
            kwargs["created_at"] = created_at
        job = CrawlJob(**kwargs)
        session.add(job)
        await session.commit()
        # Re-fetch so all server-defaults (created_at, updated_at) are populated.
        await session.refresh(job)
    return job


# ---------------------------------------------------------------------------
# Basic claim behaviour
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_claim_next_crawl_job_sets_running(session_factory) -> None:
    job = await _seed_job(session_factory, priority=1)

    async with session_factory() as session:
        claimed = await claim_next_crawl_job(session)
        await session.commit()

    assert claimed is not None
    assert claimed.id == job.id
    assert claimed.status == "running"


@pytest.mark.asyncio
async def test_claim_next_crawl_job_respects_priority(session_factory) -> None:
    low = await _seed_job(session_factory, priority=0)
    high = await _seed_job(session_factory, priority=10)

    async with session_factory() as session:
        claimed = await claim_next_crawl_job(session)
        await session.commit()

    assert claimed is not None
    assert claimed.id == high.id
    assert claimed.id != low.id


@pytest.mark.asyncio
async def test_claim_next_crawl_job_returns_none_when_empty(session_factory) -> None:
    async with session_factory() as session:
        claimed = await claim_next_crawl_job(session)
    assert claimed is None


# ---------------------------------------------------------------------------
# Skip: already crawled (signal_snapshot exists)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_claim_skips_job_when_snapshot_exists(session_factory) -> None:
    """A queued job whose URL already has a signal_snapshot should be skipped."""
    now = datetime.now(UTC)
    # Create queued job first (older timestamp).
    job = await _seed_job(session_factory, created_at=now - timedelta(minutes=5))

    # Insert a signal_snapshot for the same URL (newer than the queued job).
    async with session_factory() as session:
        snapshot = SignalSnapshot(
            url_id=job.url_id,
            version=1,
            signals={"schema_version": "v1"},
            evidence_hash="a" * 64,
            persona="direct",
            crawl_duration_sec=1.5,
        )
        session.add(snapshot)
        await session.commit()

    async with session_factory() as session:
        claimed = await claim_next_crawl_job(session)

    assert claimed is None, "Job should be skipped — URL already has a snapshot"


@pytest.mark.asyncio
async def test_claim_processes_job_when_snapshot_is_older(session_factory) -> None:
    """A queued job created AFTER the existing snapshot is eligible (re-crawl intent)."""
    now = datetime.now(UTC)
    job = await _seed_job(session_factory, created_at=now + timedelta(minutes=5))

    async with session_factory() as session:
        snapshot = SignalSnapshot(
            url_id=job.url_id,
            version=1,
            signals={"schema_version": "v1"},
            evidence_hash="b" * 64,
            persona="direct",
        )
        session.add(snapshot)
        await session.commit()

    async with session_factory() as session:
        claimed = await claim_next_crawl_job(session)
        await session.commit()

    assert claimed is not None
    assert claimed.id == job.id, "Re-crawl job (newer than snapshot) should be claimed"


# ---------------------------------------------------------------------------
# Skip: permanent failure exists
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_claim_skips_job_when_permanent_failure_is_newer(session_factory) -> None:
    """A queued job should be skipped if a permanent failure was recorded after it."""
    now = datetime.now(UTC)
    # Create the URL once and reuse its url_id.
    url_id = uuid.uuid4()
    async with session_factory() as session:
        session.add(
            Url(
                id=url_id,
                url="https://gone.example.com/",
                normalized_url="https://gone.example.com/",
                url_hash=f"hash-{url_id.hex[:12]}",
                domain="gone.example.com",
            )
        )
        await session.commit()

    # Old queued job (T1).
    old_job = await _seed_job(
        session_factory, url_id=url_id, created_at=now - timedelta(minutes=10)
    )

    # Permanent failure job concluded AFTER the queued job was created (T2 > T1).
    failed_job = await _seed_job(
        session_factory,
        url_id=url_id,
        status="failed",
        crawl_error_type="not_found",
        created_at=now - timedelta(minutes=9),
    )
    # Manually set updated_at to after the queued job.
    async with session_factory() as session:
        pf = await session.get(CrawlJob, failed_job.id)
        pf.updated_at = now  # type: ignore[assignment]
        await session.commit()

    async with session_factory() as session:
        claimed = await claim_next_crawl_job(session)

    assert claimed is None, (
        f"Job {old_job.id} should be skipped — permanent failure (not_found) concluded after it"
    )


@pytest.mark.asyncio
async def test_claim_processes_new_job_after_permanent_failure(session_factory) -> None:
    """A job created AFTER a permanent failure is eligible — 'until it changes' semantics."""
    now = datetime.now(UTC)
    url_id = uuid.uuid4()
    async with session_factory() as session:
        session.add(
            Url(
                id=url_id,
                url="https://gone.example.com/",
                normalized_url="https://gone.example.com/",
                url_hash=f"hash-{url_id.hex[:12]}",
                domain="gone.example.com",
            )
        )
        await session.commit()

    # Permanent failure concluded at T1.
    failed_job = await _seed_job(
        session_factory,
        url_id=url_id,
        status="failed",
        crawl_error_type="not_found",
        created_at=now - timedelta(minutes=10),
    )
    async with session_factory() as session:
        pf = await session.get(CrawlJob, failed_job.id)
        pf.updated_at = now - timedelta(minutes=5)  # type: ignore[assignment]
        await session.commit()

    # New queued job created at T2 > T1 (re-submission after potential URL fix).
    new_job = await _seed_job(
        session_factory,
        url_id=url_id,
        created_at=now,  # newer than the failure's updated_at
    )

    async with session_factory() as session:
        claimed = await claim_next_crawl_job(session)
        await session.commit()

    assert claimed is not None
    assert claimed.id == new_job.id, (
        "Re-submitted job (newer than permanent failure) should be claimed"
    )


# ---------------------------------------------------------------------------
# mark_job_failed with crawl_error_type
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mark_job_completed_and_failed(session_factory) -> None:
    job = await _seed_job(session_factory)

    async with session_factory() as session:
        await mark_job_completed(session, job.id)
        await session.commit()

    async with session_factory() as session:
        completed = await session.scalar(select(CrawlJob).where(CrawlJob.id == job.id))
        assert completed is not None
        assert completed.status == "completed"
        assert completed.error_message is None
        assert completed.crawl_error_type is None

    async with session_factory() as session:
        await mark_job_failed(session, job.id, "navigation timeout", crawl_error_type="timeout")
        await session.commit()

    async with session_factory() as session:
        failed = await session.scalar(select(CrawlJob).where(CrawlJob.id == job.id))
        assert failed is not None
        assert failed.status == "failed"
        assert failed.error_message == "navigation timeout"
        assert failed.crawl_error_type == "timeout"


@pytest.mark.asyncio
async def test_mark_job_failed_without_error_type(session_factory) -> None:
    """Backward-compatible: crawl_error_type defaults to None."""
    job = await _seed_job(session_factory)

    async with session_factory() as session:
        await mark_job_failed(session, job.id, "unknown error")
        await session.commit()

    async with session_factory() as session:
        failed = await session.scalar(select(CrawlJob).where(CrawlJob.id == job.id))
        assert failed is not None
        assert failed.crawl_error_type is None
