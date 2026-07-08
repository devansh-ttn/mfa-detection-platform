"""Postgres-backed score job consumer for ml-worker."""

from __future__ import annotations

import asyncio
import os
import uuid

import structlog
from mfa.audit.writer import write_audit_event
from mfa.db.models import SignalSnapshot
from mfa.db.session import async_session_factory
from mfa.ingestion.score_poll import (
    claim_next_score_job,
    mark_score_job_completed,
    mark_score_job_failed,
)
from mfa.scoring.writer import write_classification
from mfa_ml.scoring.artifact_loader import ScoringArtifacts
from mfa_ml.scoring.pipeline import classify_snapshot
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = structlog.get_logger(__name__)


def load_poll_interval_sec() -> float:
    return float(os.getenv("SCORE_POLL_INTERVAL_SEC", "5"))


async def process_claimed_score_job(
    job_id: uuid.UUID,
    url_id: uuid.UUID,
    signal_snapshot_id: uuid.UUID,
    *,
    artifacts: ScoringArtifacts,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> None:
    """Load snapshot, classify, persist classification + audit, complete job."""
    factory = session_factory or async_session_factory

    try:
        async with factory() as session:
            snapshot = await session.get(SignalSnapshot, signal_snapshot_id)
            if snapshot is None:
                raise LookupError(f"signal_snapshot not found: {signal_snapshot_id}")

            output = classify_snapshot(
                snapshot.signals,
                evidence_hash=snapshot.evidence_hash,
                artifacts=artifacts,
            )
            classification = await write_classification(
                session,
                url_id=url_id,
                signal_snapshot_id=signal_snapshot_id,
                output=output,
            )
            await write_audit_event(
                session,
                entity_type="classification",
                entity_id=str(classification.id),
                action="classification.scored",
                evidence_hash=output.evidence_hash,
                payload={
                    "job_id": str(job_id),
                    "url_id": str(url_id),
                    "signal_snapshot_id": str(signal_snapshot_id),
                    "tier": output.tier,
                    "mfa_score": output.mfa_score,
                    "confidence": output.confidence,
                    "classifier": output.classifier,
                },
            )
            await mark_score_job_completed(session, job_id)
            await session.commit()

    except Exception as exc:
        logger.exception(
            "score_job_process_failed",
            job_id=str(job_id),
            url_id=str(url_id),
            signal_snapshot_id=str(signal_snapshot_id),
        )
        async with factory() as session:
            await mark_score_job_failed(session, job_id, str(exc))
            await session.commit()
        raise


async def poll_and_process_once(
    *,
    artifacts: ScoringArtifacts,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> bool:
    """Claim and process one queued score job. Returns True if a job was processed."""
    factory = session_factory or async_session_factory

    async with factory() as session:
        job = await claim_next_score_job(session)
        if job is None:
            return False
        job_id = job.id
        url_id = job.url_id
        signal_snapshot_id = job.signal_snapshot_id
        await session.commit()

    await process_claimed_score_job(
        job_id,
        url_id,
        signal_snapshot_id,
        artifacts=artifacts,
        session_factory=factory,
    )
    return True


async def run_consumer_loop(
    *,
    artifacts: ScoringArtifacts,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
    poll_interval_sec: float | None = None,
    shutdown_event: asyncio.Event | None = None,
) -> None:
    """Poll Postgres for queued score jobs until *shutdown_event* is set."""
    interval = poll_interval_sec if poll_interval_sec is not None else load_poll_interval_sec()
    stop = shutdown_event or asyncio.Event()

    logger.info("ml_consumer_started", poll_interval_sec=interval)

    while not stop.is_set():
        try:
            processed = await poll_and_process_once(
                artifacts=artifacts,
                session_factory=session_factory,
            )
        except Exception:
            logger.exception("ml_consumer_loop_error")
            processed = False

        if processed or stop.is_set():
            continue

        try:
            await asyncio.wait_for(stop.wait(), timeout=interval)
        except TimeoutError:
            continue

    logger.info("ml_consumer_stopped")
