"""Postgres-backed crawl job consumer for crawler-worker."""

from __future__ import annotations

import asyncio
import os
import uuid

import structlog
from mfa.db.session import async_session_factory
from mfa.ingestion.job_poll import claim_next_crawl_job, mark_job_completed, mark_job_failed
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

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
    """Run crawl + persist for a claimed job and update crawl_jobs status."""
    factory = session_factory or async_session_factory
    try:
        await crawl_and_persist(url_id, session_factory=factory)
        async with factory() as session:
            await mark_job_completed(session, job_id)
            await session.commit()
    except Exception as exc:
        logger.exception("crawl_job_process_failed", job_id=str(job_id), url_id=str(url_id))
        async with factory() as session:
            await mark_job_failed(session, job_id, str(exc))
            await session.commit()
        raise


async def poll_and_process_once(
    *,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> bool:
    """Claim and process one queued job. Returns True if a job was processed."""
    factory = session_factory or async_session_factory

    async with factory() as session:
        job = await claim_next_crawl_job(session)
        if job is None:
            return False
        job_id = job.id
        url_id = job.url_id
        await session.commit()

    await process_claimed_job(job_id, url_id, session_factory=factory)
    return True


async def run_consumer_loop(
    *,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
    poll_interval_sec: float | None = None,
    shutdown_event: asyncio.Event | None = None,
) -> None:
    """Poll Postgres for queued crawl jobs until *shutdown_event* is set."""
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
