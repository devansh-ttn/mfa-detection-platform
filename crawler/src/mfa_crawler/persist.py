"""Persist crawl results to signal_snapshots (Postgres JSONB) and local evidence artifacts."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path

import structlog
from mfa.db.models import SignalSnapshot, Url
from mfa.db.session import async_session_factory
from mfa.schemas.signals import Persona, SignalSnapshotPayload, compute_evidence_hash
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mfa_crawler.artifacts import write_evidence_artifacts
from mfa_crawler.crawl import CrawlResult, crawl_url

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class PersistedSnapshot:
    snapshot_id: uuid.UUID
    url_id: uuid.UUID
    version: int
    evidence_hash: str
    persona: Persona
    crawl_duration_sec: float
    payload: SignalSnapshotPayload
    artifact_dir: Path | None = None


async def next_snapshot_version(session: AsyncSession, url_id: uuid.UUID) -> int:
    """Return the next monotonic version for *url_id* (starts at 1)."""
    current_max = await session.scalar(
        select(func.max(SignalSnapshot.version)).where(SignalSnapshot.url_id == url_id)
    )
    return int(current_max or 0) + 1


async def persist_signal_snapshot(
    session: AsyncSession,
    *,
    url_id: uuid.UUID,
    payload: SignalSnapshotPayload,
    crawl_duration_sec: float,
    persona: Persona = "direct",
    crawl_result: CrawlResult | None = None,
    write_artifacts: bool = True,
    evidence_base_dir: Path | None = None,
) -> PersistedSnapshot:
    """Insert a versioned signal_snapshots row with computed evidence_hash."""
    url = await session.get(Url, url_id)
    if url is None:
        raise LookupError(f"url_id not found: {url_id}")

    signals = payload.to_db()
    evidence_hash = compute_evidence_hash(signals)
    version = await next_snapshot_version(session, url_id)

    snapshot = SignalSnapshot(
        url_id=url_id,
        version=version,
        signals=signals,
        evidence_hash=evidence_hash,
        persona=persona,
        crawl_duration_sec=crawl_duration_sec,
    )
    session.add(snapshot)
    await session.flush()

    artifact_dir: Path | None = None
    if write_artifacts and crawl_result is not None:
        artifact_dir = write_evidence_artifacts(
            url_id=url_id,
            version=version,
            html=crawl_result.html,
            screenshot_png=crawl_result.screenshot_png,
            dom_metrics=payload.features.model_dump(mode="json"),
            base_dir=evidence_base_dir,
        )

    logger.info(
        "signal_snapshot_persisted",
        url_id=str(url_id),
        snapshot_id=str(snapshot.id),
        version=version,
        persona=persona,
        evidence_hash=evidence_hash,
        crawl_duration_sec=round(crawl_duration_sec, 3),
        artifact_dir=str(artifact_dir) if artifact_dir else None,
    )

    return PersistedSnapshot(
        snapshot_id=snapshot.id,
        url_id=url_id,
        version=version,
        evidence_hash=evidence_hash,
        persona=persona,
        crawl_duration_sec=crawl_duration_sec,
        payload=payload,
        artifact_dir=artifact_dir,
    )


async def crawl_and_persist(
    url_id: uuid.UUID,
    *,
    persona: Persona = "direct",
    session_factory: async_sessionmaker[AsyncSession] | None = None,
    write_artifacts: bool = True,
    evidence_base_dir: Path | None = None,
) -> PersistedSnapshot:
    """Crawl the URL record for *url_id* and persist snapshot + local evidence artifacts."""
    factory = session_factory or async_session_factory

    async with factory() as session:
        url = await session.get(Url, url_id)
        if url is None:
            raise LookupError(f"url_id not found: {url_id}")
        target_url = url.url

    crawl_result = await crawl_url(target_url, persona=persona)

    async with factory() as session:
        result = await persist_signal_snapshot(
            session,
            url_id=url_id,
            payload=crawl_result.payload,
            crawl_duration_sec=crawl_result.duration_sec,
            persona=persona,
            crawl_result=crawl_result,
            write_artifacts=write_artifacts,
            evidence_base_dir=evidence_base_dir,
        )
        await session.commit()
        return result
