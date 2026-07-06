"""Tests for Postgres-backed crawl job polling."""

from __future__ import annotations

import os
import uuid

import pytest
from mfa.db.models import Base, CrawlJob, Url
from mfa.ingestion.job_poll import claim_next_crawl_job, mark_job_completed, mark_job_failed
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

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
) -> CrawlJob:
    url_id = uuid.uuid4()
    job_id = uuid.uuid4()
    async with session_factory() as session:
        session.add(
            Url(
                id=url_id,
                url="https://example.com/article",
                normalized_url="https://example.com/article",
                url_hash=f"hash-{url_id.hex[:12]}",
                domain="example.com",
            )
        )
        job = CrawlJob(
            id=job_id,
            url_id=url_id,
            status=status,
            priority=priority,
            idempotency_key=f"key-{job_id.hex[:12]}",
        )
        session.add(job)
        await session.commit()
    return job


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

    async with session_factory() as session:
        await mark_job_failed(session, job.id, "navigation timeout")
        await session.commit()

    async with session_factory() as session:
        failed = await session.scalar(select(CrawlJob).where(CrawlJob.id == job.id))
        assert failed is not None
        assert failed.status == "failed"
        assert failed.error_message == "navigation timeout"
