"""Tests for Postgres-backed score job polling."""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from mfa.db.models import Base, Classification, ScoreJob, SignalSnapshot, Url
from mfa.ingestion.score_poll import (
    claim_next_score_job,
    enqueue_score_job,
    mark_score_job_completed,
    mark_score_job_failed,
)

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


async def _seed_url_and_snapshot(session_factory) -> tuple[uuid.UUID, uuid.UUID]:
    url_id = uuid.uuid4()
    snapshot_id = uuid.uuid4()
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
        session.add(
            SignalSnapshot(
                id=snapshot_id,
                url_id=url_id,
                version=1,
                signals={"ad_to_content_ratio": 0.5, "content_word_count": 100},
                evidence_hash="a" * 64,
                persona="direct",
            )
        )
        await session.commit()
    return url_id, snapshot_id


@pytest.mark.asyncio
async def test_enqueue_score_job_creates_queued_row(session_factory) -> None:
    url_id, snapshot_id = await _seed_url_and_snapshot(session_factory)

    async with session_factory() as session:
        job = await enqueue_score_job(session, url_id, snapshot_id)
        await session.commit()

    assert job.status == "queued"
    assert job.signal_snapshot_id == snapshot_id


@pytest.mark.asyncio
async def test_enqueue_score_job_is_idempotent(session_factory) -> None:
    url_id, snapshot_id = await _seed_url_and_snapshot(session_factory)

    async with session_factory() as session:
        first = await enqueue_score_job(session, url_id, snapshot_id)
        second = await enqueue_score_job(session, url_id, snapshot_id)
        await session.commit()

    assert first.id == second.id


@pytest.mark.asyncio
async def test_claim_next_score_job_sets_running(session_factory) -> None:
    url_id, snapshot_id = await _seed_url_and_snapshot(session_factory)
    async with session_factory() as session:
        await enqueue_score_job(session, url_id, snapshot_id)
        await session.commit()

    async with session_factory() as session:
        claimed = await claim_next_score_job(session)
        await session.commit()

    assert claimed is not None
    assert claimed.status == "running"


@pytest.mark.asyncio
async def test_claim_skips_when_classification_exists(session_factory) -> None:
    url_id, snapshot_id = await _seed_url_and_snapshot(session_factory)
    now = datetime.now(UTC)

    async with session_factory() as session:
        job = await enqueue_score_job(session, url_id, snapshot_id)
        job.created_at = now - timedelta(minutes=5)  # type: ignore[assignment]
        session.add(
            Classification(
                url_id=url_id,
                signal_snapshot_id=snapshot_id,
                tier="Non_MFA",
                mfa_score=0.1,
                confidence="high",
                top_signals=[],
                explanation="ok",
                evidence_hash="b" * 64,
                classifier="xgboost",
                schema_version="v1",
            )
        )
        await session.commit()

    async with session_factory() as session:
        claimed = await claim_next_score_job(session)

    assert claimed is None


@pytest.mark.asyncio
async def test_mark_score_job_completed_and_failed(session_factory) -> None:
    url_id, snapshot_id = await _seed_url_and_snapshot(session_factory)
    async with session_factory() as session:
        job = await enqueue_score_job(session, url_id, snapshot_id)
        await session.commit()
        job_id = job.id

    async with session_factory() as session:
        await mark_score_job_completed(session, job_id)
        await session.commit()

    async with session_factory() as session:
        completed = await session.scalar(select(ScoreJob).where(ScoreJob.id == job_id))
        assert completed is not None
        assert completed.status == "completed"

    async with session_factory() as session:
        await mark_score_job_failed(session, job_id, "classify error")
        await session.commit()

    async with session_factory() as session:
        failed = await session.scalar(select(ScoreJob).where(ScoreJob.id == job_id))
        assert failed is not None
        assert failed.status == "failed"
        assert failed.error_message == "classify error"
