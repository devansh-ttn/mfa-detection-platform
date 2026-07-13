"""Postgres-backed crawl job consumer for crawler-worker."""

from __future__ import annotations

import asyncio
import os
import uuid

import structlog
from mfa.audit.writer import write_audit_event
from mfa.db.models import CrawlJob
from mfa.db.session import async_session_factory
from mfa.ingestion.job_poll import (
    claim_crawl_job_by_id,
    claim_next_crawl_job,
    mark_job_completed,
    mark_job_failed,
)
from mfa.ingestion.sqs_transport import (
    crawl_queue_url,
    delete_message,
    receive_job_messages,
    resolve_queue_for_message,
    sqs_enabled,
)
from mfa.ingestion.score_poll import enqueue_score_job
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mfa_crawler.errors import PERMANENT_ERROR_TYPES, CrawlError
from mfa_crawler.persist import crawl_and_persist

logger = structlog.get_logger(__name__)


def load_poll_interval_sec() -> float:
    return float(os.getenv("CRAWL_POLL_INTERVAL_SEC", "5"))


async def process_claimed_job(
    job_id: uuid.UUID,
    url_id: uuid.UUID,
    *,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> None:
    """Run crawl + persist for a claimed job and update crawl_jobs status.

    Error handling:
    - ``CrawlError`` subclasses carry an ``error_type`` that is written to
      ``crawl_jobs.crawl_error_type`` for future skip-logic.
    - Permanent errors (``not_found``, ``invalid_url``, ``robots_denied``) are
      logged at WARNING and *not* re-raised — they are expected outcomes.
    - Transient errors (``timeout``, ``http_error``, generic) are logged at
      ERROR and re-raised so the consumer loop can apply back-off.
    - Unknown / unexpected exceptions are always re-raised.
    """
    factory = session_factory or async_session_factory
    try:
        persisted = await crawl_and_persist(url_id, session_factory=factory)
        async with factory() as session:
            await mark_job_completed(session, job_id)
            await enqueue_score_job(
                session,
                url_id,
                persisted.snapshot_id,
            )
            await write_audit_event(
                session,
                entity_type="url",
                entity_id=str(url_id),
                action="crawl.completed",
                evidence_hash=persisted.evidence_hash,
                payload={
                    "job_id": str(job_id),
                    "signal_snapshot_id": str(persisted.snapshot_id),
                    "version": persisted.version,
                    "persona": persisted.persona,
                },
            )
            await session.commit()

    except CrawlError as exc:
        is_permanent = exc.error_type in PERMANENT_ERROR_TYPES
        log = logger.warning if is_permanent else logger.error
        log(
            "crawl_job_failed",
            job_id=str(job_id),
            url_id=str(url_id),
            error_type=exc.error_type,
            permanent=is_permanent,
            error=str(exc),
        )
        async with factory() as session:
            await mark_job_failed(
                session,
                job_id,
                str(exc),
                crawl_error_type=exc.error_type,
            )
            await session.commit()
        if not is_permanent:
            raise

    except Exception as exc:
        logger.exception("crawl_job_process_failed", job_id=str(job_id), url_id=str(url_id))
        async with factory() as session:
            await mark_job_failed(session, job_id, str(exc))
            await session.commit()
        raise


async def _claim_from_sqs(
    session: AsyncSession,
) -> tuple[CrawlJob | None, str | None]:
    """Receive SQS crawl message and claim matching Postgres job."""
    queue_urls = list(
        dict.fromkeys(
            url
            for url in (
                crawl_queue_url(priority=0),
                crawl_queue_url(priority=1),
            )
            if url
        )
    )
    messages = receive_job_messages(queue_urls, max_messages=1, wait_seconds=5)
    for msg in messages:
        if msg.job_type != "crawl":
            delete_message(resolve_queue_for_message(msg), msg.receipt_handle)
            continue
        job = await claim_crawl_job_by_id(session, msg.job_id)
        if job is None:
            delete_message(resolve_queue_for_message(msg), msg.receipt_handle)
            continue
        return job, msg.receipt_handle
    return None, None


async def poll_and_process_once(
    *,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> bool:
    """Claim and process one queued job. Returns True if a job was processed."""
    factory = session_factory or async_session_factory

    receipt_handle: str | None = None
    queue_url: str | None = None

    async with factory() as session:
        if sqs_enabled():
            job, receipt_handle = await _claim_from_sqs(session)
        else:
            job = await claim_next_crawl_job(session)
        if job is None:
            return False
        job_id = job.id
        url_id = job.url_id
        if sqs_enabled() and receipt_handle:
            queue_url = crawl_queue_url(priority=job.priority)
        await session.commit()

    try:
        await process_claimed_job(job_id, url_id, session_factory=factory)
    finally:
        if queue_url and receipt_handle:
            delete_message(queue_url, receipt_handle)
    return True


async def run_consumer_loop(
    *,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
    poll_interval_sec: float | None = None,
    shutdown_event: asyncio.Event | None = None,
) -> None:
    """Poll Postgres for queued crawl jobs until *shutdown_event* is set.

    Back-off: waits ``poll_interval_sec`` only when the queue is empty or a
    transient error occurred.  Permanent failures (not_found, invalid_url) are
    silently swallowed so the loop continues immediately to the next job.
    """
    interval = poll_interval_sec if poll_interval_sec is not None else load_poll_interval_sec()
    stop = shutdown_event or asyncio.Event()

    logger.info("crawler_consumer_started", poll_interval_sec=interval)

    while not stop.is_set():
        try:
            processed = await poll_and_process_once(session_factory=session_factory)
        except Exception:
            logger.exception("crawl_consumer_loop_error")
            processed = False

        if processed or stop.is_set():
            continue

        try:
            await asyncio.wait_for(stop.wait(), timeout=interval)
        except TimeoutError:
            continue

    logger.info("crawler_consumer_stopped")
