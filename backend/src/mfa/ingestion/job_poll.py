"""Postgres-backed crawl job polling for worker consumers.

Workers claim queued rows directly from crawl_jobs (POC-simple durable queue).
In-memory enqueue in the API process is optional; jobs remain pollable after restart.
"""

from __future__ import annotations

import uuid

import structlog
from mfa.db.models import CrawlJob
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)


async def claim_next_crawl_job(session: AsyncSession) -> CrawlJob | None:
    """Atomically claim the highest-priority queued job, or None if the queue is empty."""
    job = await session.scalar(
        select(CrawlJob)
        .where(CrawlJob.status == "queued")
        .order_by(CrawlJob.priority.desc(), CrawlJob.created_at.asc())
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    if job is None:
        return None

    job.status = "running"
    await session.flush()
    logger.info("crawl_job_claimed", job_id=str(job.id), url_id=str(job.url_id))
    return job


async def mark_job_completed(session: AsyncSession, job_id: uuid.UUID) -> CrawlJob:
    job = await _require_job(session, job_id)
    job.status = "completed"
    job.error_message = None
    await session.flush()
    logger.info("crawl_job_completed", job_id=str(job_id))
    return job


async def mark_job_failed(
    session: AsyncSession,
    job_id: uuid.UUID,
    error_message: str,
) -> CrawlJob:
    job = await _require_job(session, job_id)
    job.status = "failed"
    job.error_message = error_message[:4000]
    await session.flush()
    logger.info("crawl_job_failed", job_id=str(job_id), error=job.error_message)
    return job


async def _require_job(session: AsyncSession, job_id: uuid.UUID) -> CrawlJob:
    job = await session.get(CrawlJob, job_id)
    if job is None:
        raise LookupError(f"crawl_job not found: {job_id}")
    return job
