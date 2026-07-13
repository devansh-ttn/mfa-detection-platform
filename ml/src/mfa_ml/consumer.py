"""Postgres-backed score job consumer for ml-worker."""

from __future__ import annotations

import asyncio
import os
import uuid

import structlog
from mfa.audit.writer import write_audit_event
from mfa.cache.redis_cache import get_domain_cache
from mfa.db.models import ScoreJob, SignalSnapshot, Url
from mfa.db.session import async_session_factory
from mfa.ingestion.score_poll import (
    claim_next_score_job,
    claim_score_job_by_id,
    mark_score_job_completed,
    mark_score_job_failed,
)
from mfa.ingestion.sqs_transport import (
    delete_message,
    receive_job_messages,
    resolve_queue_for_message,
    score_queue_url,
    sqs_enabled,
)
from mfa.scoring.llm_explanation import generate_llm_explanation
from mfa.scoring.writer import write_classification
from mfa.rag.indexer import index_url_entities
from mfa.rag.opensearch_client import get_opensearch_client
from mfa_ml.scoring.artifact_loader import ScoringArtifacts
from mfa_ml.scoring.pipeline import classify_snapshot, extract_features
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = structlog.get_logger(__name__)


def load_poll_interval_sec() -> float:
    return float(os.getenv("SCORE_POLL_INTERVAL_SEC", "5"))


def _enhance_explanation(
    output,
    *,
    signals: dict,
) -> str:
    """Apply LLM explanation layer (ADR-001) with template fallback."""
    features = extract_features(signals)
    top_signals = [s.model_dump(mode="json") for s in output.top_signals]
    return generate_llm_explanation(
        tier=output.tier,
        mfa_score=output.mfa_score,
        top_signals=top_signals,
        signals_snapshot=features,
        template_explanation=output.explanation,
    )


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
            template_explanation = output.explanation
            explanation = _enhance_explanation(output, signals=snapshot.signals)
            if explanation != template_explanation:
                output = output.model_copy(update={"explanation": explanation})

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
            if explanation != template_explanation:
                await write_audit_event(
                    session,
                    entity_type="classification",
                    entity_id=str(classification.id),
                    action="explanation.llm",
                    evidence_hash=output.evidence_hash,
                    payload={
                        "classification_id": str(classification.id),
                        "bedrock_enabled": os.getenv("BEDROCK_ENABLED", "").lower()
                        in {"1", "true", "yes"},
                    },
                )

            url_row = await session.get(Url, url_id)
            if url_row is not None:
                cache = get_domain_cache()
                cache.set(
                    url_row.domain,
                    tier=output.tier,
                    confidence=output.confidence,
                    mfa_score=output.mfa_score,
                    evidence_hash=output.evidence_hash,
                    url_id=str(url_id),
                )

            await mark_score_job_completed(session, job_id)
            if get_opensearch_client().enabled:
                await index_url_entities(session, url_id)
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


async def _claim_from_sqs(
    session: AsyncSession,
) -> tuple[ScoreJob | None, str | None]:
    """Receive SQS score message and claim matching Postgres job."""
    url = score_queue_url()
    if not url:
        return None, None
    messages = receive_job_messages([url], max_messages=1, wait_seconds=5)
    for msg in messages:
        if msg.job_type != "score":
            delete_message(resolve_queue_for_message(msg), msg.receipt_handle)
            continue
        job = await claim_score_job_by_id(session, msg.job_id)
        if job is None:
            delete_message(resolve_queue_for_message(msg), msg.receipt_handle)
            continue
        return job, msg.receipt_handle
    return None, None


async def poll_and_process_once(
    *,
    artifacts: ScoringArtifacts,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> bool:
    """Claim and process one queued score job. Returns True if a job was processed."""
    factory = session_factory or async_session_factory

    receipt_handle: str | None = None
    queue_url: str | None = None

    async with factory() as session:
        if sqs_enabled():
            job, receipt_handle = await _claim_from_sqs(session)
        else:
            job = await claim_next_score_job(session)
        if job is None:
            return False
        job_id = job.id
        url_id = job.url_id
        signal_snapshot_id = job.signal_snapshot_id
        if sqs_enabled() and receipt_handle:
            queue_url = score_queue_url()
        await session.commit()

    try:
        await process_claimed_score_job(
            job_id,
            url_id,
            signal_snapshot_id,
            artifacts=artifacts,
            session_factory=factory,
        )
    finally:
        if queue_url and receipt_handle:
            delete_message(queue_url, receipt_handle)
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
