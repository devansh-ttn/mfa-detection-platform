"""Postgres-backed crawl job polling for worker consumers.

Workers claim queued rows directly from crawl_jobs (POC-simple durable queue).
In-memory enqueue in the API process is optional; jobs remain pollable after restart.

## Skip logic in ``claim_next_crawl_job``

A queued job is *skipped* (not claimed) when the URL has already been resolved:

1. **Already crawled**: a ``signal_snapshots`` row exists whose ``created_at`` is
   *newer* than the queued job's ``created_at``. This means a prior run already
   produced a usable snapshot, so the job is redundant.

2. **Permanently failed**: a ``crawl_jobs`` row with a permanent ``crawl_error_type``
   (``not_found``, ``invalid_url``, ``robots_denied``) has ``updated_at`` *newer*
   than the queued job's ``created_at``. This means the URL was confirmed broken
   after this job was queued.

Re-crawl semantics ("until it changes"):
   Submitting the same URL again via the ingestion API creates a new crawl_jobs
   row with a **newer** ``created_at``.  Both skip conditions use
   ``> job.created_at`` so a fresh submission always clears the skip gate.
"""

from __future__ import annotations

import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from mfa.db.models import CrawlJob, SignalSnapshot

logger = structlog.get_logger(__name__)

# These error types will never self-resolve; skip any queued job for the same URL
# whose created_at is older than the permanent failure's updated_at.
_PERMANENT_ERROR_TYPES: tuple[str, ...] = ("not_found", "invalid_url", "robots_denied")


async def claim_next_crawl_job(session: AsyncSession) -> CrawlJob | None:
    """Atomically claim the next processable queued job, or None if none available.

    Respects the skip logic described in the module docstring:
    - Skips URLs that have a signal_snapshot newer than the queued job.
    - Skips URLs that have a permanent-failure job concluded after the queued job
      was created.
    """
    PermanentFailure = aliased(CrawlJob, name="perm_failure")

    # Exists-clause: URL was already successfully crawled after this job was queued.
    already_crawled = (
        select(SignalSnapshot.id)
        .where(SignalSnapshot.url_id == CrawlJob.url_id)
        .where(SignalSnapshot.created_at > CrawlJob.created_at)
        .correlate(CrawlJob)
        .exists()
    )

    # Exists-clause: URL was confirmed broken (permanent error) after this job was queued.
    already_perm_failed = (
        select(PermanentFailure.id)
        .where(PermanentFailure.url_id == CrawlJob.url_id)
        .where(PermanentFailure.id != CrawlJob.id)
        .where(PermanentFailure.crawl_error_type.in_(_PERMANENT_ERROR_TYPES))
        .where(PermanentFailure.updated_at > CrawlJob.created_at)
        .correlate(CrawlJob)
        .exists()
    )

    job = await session.scalar(
        select(CrawlJob)
        .where(CrawlJob.status == "queued")
        .where(~already_crawled)
        .where(~already_perm_failed)
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
    """Mark a job as completed and clear any previous error state."""
    job = await _require_job(session, job_id)
    job.status = "completed"
    job.error_message = None
    job.crawl_error_type = None
    await session.flush()
    logger.info("crawl_job_completed", job_id=str(job_id))
    return job


async def mark_job_failed(
    session: AsyncSession,
    job_id: uuid.UUID,
    error_message: str,
    *,
    crawl_error_type: str | None = None,
) -> CrawlJob:
    """Mark a job as failed.

    Args:
        session: Active async session.
        job_id: The job to update.
        error_message: Human-readable error summary (truncated to 4 000 chars).
        crawl_error_type: Optional classification; drives skip logic for future
            queued jobs on the same URL.  Pass a value from
            ``mfa_crawler.errors.CrawlErrorType`` (or ``None`` for unknown).
    """
    job = await _require_job(session, job_id)
    job.status = "failed"
    job.error_message = error_message[:4000]
    job.crawl_error_type = crawl_error_type
    await session.flush()
    logger.info(
        "crawl_job_failed",
        job_id=str(job_id),
        crawl_error_type=crawl_error_type,
        error=job.error_message,
    )
    return job


async def _require_job(session: AsyncSession, job_id: uuid.UUID) -> CrawlJob:
    job = await session.get(CrawlJob, job_id)
    if job is None:
        raise LookupError(f"crawl_job not found: {job_id}")
    return job
