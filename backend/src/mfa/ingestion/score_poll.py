"""Postgres-backed score job polling for ml-worker consumers.

Workers claim queued rows from score_jobs (POC-simple durable queue).
Enqueue is idempotent per signal_snapshot_id via unique constraint.

## Skip logic in ``claim_next_score_job``

A queued job is *skipped* when a classification already exists for the same
``signal_snapshot_id``, or when a newer classification exists for the URL
(created after the job was queued).
"""

from __future__ import annotations

import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from mfa.db.models import Classification, ScoreJob
from mfa.ingestion.sqs_transport import publish_score_job, sqs_enabled

logger = structlog.get_logger(__name__)


async def enqueue_score_job(
    session: AsyncSession,
    url_id: uuid.UUID,
    signal_snapshot_id: uuid.UUID,
    *,
    priority: int = 0,
) -> ScoreJob:
    """Enqueue a score job for *signal_snapshot_id* (idempotent)."""
    existing = await session.scalar(
        select(ScoreJob).where(ScoreJob.signal_snapshot_id == signal_snapshot_id)
    )
    if existing is not None:
        logger.debug(
            "score_job_already_enqueued",
            job_id=str(existing.id),
            signal_snapshot_id=str(signal_snapshot_id),
        )
        return existing

    job = ScoreJob(
        url_id=url_id,
        signal_snapshot_id=signal_snapshot_id,
        status="queued",
        priority=priority,
    )
    session.add(job)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        existing = await session.scalar(
            select(ScoreJob).where(ScoreJob.signal_snapshot_id == signal_snapshot_id)
        )
        if existing is None:
            raise
        return existing

    logger.info(
        "score_job_enqueued",
        job_id=str(job.id),
        url_id=str(url_id),
        signal_snapshot_id=str(signal_snapshot_id),
    )
    if sqs_enabled():
        publish_score_job(
            job_id=job.id,
            url_id=url_id,
            signal_snapshot_id=signal_snapshot_id,
            priority=priority,
        )
    return job


async def claim_score_job_by_id(session: AsyncSession, job_id: uuid.UUID) -> ScoreJob | None:
    """Claim a specific queued score job (SQS consumer path)."""
    job = await session.scalar(
        select(ScoreJob)
        .where(ScoreJob.id == job_id)
        .where(ScoreJob.status == "queued")
        .with_for_update(skip_locked=True)
    )
    if job is None:
        return None
    job.status = "running"
    await session.flush()
    logger.info(
        "score_job_claimed",
        job_id=str(job.id),
        url_id=str(job.url_id),
        signal_snapshot_id=str(job.signal_snapshot_id),
        source="sqs",
    )
    return job


async def claim_next_score_job(session: AsyncSession) -> ScoreJob | None:
    """Atomically claim the next processable queued score job, or None."""
    already_scored_snapshot = (
        select(Classification.id)
        .where(Classification.signal_snapshot_id == ScoreJob.signal_snapshot_id)
        .correlate(ScoreJob)
        .exists()
    )

    already_scored_newer = (
        select(Classification.id)
        .where(Classification.url_id == ScoreJob.url_id)
        .where(Classification.created_at > ScoreJob.created_at)
        .correlate(ScoreJob)
        .exists()
    )

    job = await session.scalar(
        select(ScoreJob)
        .where(ScoreJob.status == "queued")
        .where(~already_scored_snapshot)
        .where(~already_scored_newer)
        .order_by(ScoreJob.priority.desc(), ScoreJob.created_at.asc())
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    if job is None:
        return None

    job.status = "running"
    await session.flush()
    logger.info(
        "score_job_claimed",
        job_id=str(job.id),
        url_id=str(job.url_id),
        signal_snapshot_id=str(job.signal_snapshot_id),
    )
    return job


async def mark_score_job_completed(session: AsyncSession, job_id: uuid.UUID) -> ScoreJob:
    """Mark a score job as completed and clear any previous error state."""
    job = await _require_job(session, job_id)
    job.status = "completed"
    job.error_message = None
    await session.flush()
    logger.info("score_job_completed", job_id=str(job_id))
    return job


async def mark_score_job_failed(
    session: AsyncSession,
    job_id: uuid.UUID,
    error_message: str,
) -> ScoreJob:
    """Mark a score job as failed."""
    job = await _require_job(session, job_id)
    job.status = "failed"
    job.error_message = error_message[:4000]
    await session.flush()
    logger.info("score_job_failed", job_id=str(job_id), error=job.error_message)
    return job


async def _require_job(session: AsyncSession, job_id: uuid.UUID) -> ScoreJob:
    job = await session.get(ScoreJob, job_id)
    if job is None:
        raise LookupError(f"score_job not found: {job_id}")
    return job
