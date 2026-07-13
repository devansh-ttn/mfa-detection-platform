"""OpenSearch indexing worker — index classifications and snapshots (MVP-3.2)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mfa.db.models import Classification, ReviewOverride, SignalSnapshot, Url
from mfa.rag.opensearch_client import get_opensearch_client

logger = structlog.get_logger(__name__)


def _base_doc(
    *,
    chunk_id: str,
    doc_type: str,
    url: Url,
    excerpt: str,
    content: dict[str, Any],
    evidence_hash: str | None = None,
    tier: str | None = None,
) -> dict[str, Any]:
    return {
        "chunk_id": chunk_id,
        "doc_type": doc_type,
        "domain": url.domain,
        "url_id": str(url.id),
        "url": url.normalized_url,
        "tier": tier,
        "excerpt": excerpt[:2000],
        "content": content,
        "evidence_hash": evidence_hash,
        "indexed_at": datetime.now(UTC).isoformat(),
    }


def index_classification_doc(cls: Classification, url: Url) -> None:
    client = get_opensearch_client()
    if not client.enabled:
        return
    chunk_id = f"classification:{cls.id}"
    doc = _base_doc(
        chunk_id=chunk_id,
        doc_type="explanation",
        url=url,
        excerpt=cls.explanation,
        content={
            "tier": cls.tier,
            "mfa_score": cls.mfa_score,
            "confidence": cls.confidence,
            "explanation": cls.explanation,
            "top_signals": cls.top_signals,
            "evidence_hash": cls.evidence_hash,
        },
        evidence_hash=cls.evidence_hash,
        tier=cls.tier,
    )
    client.index_document(doc, doc_id=chunk_id)


def index_signal_snapshot_doc(snapshot: SignalSnapshot, url: Url) -> None:
    client = get_opensearch_client()
    if not client.enabled:
        return
    chunk_id = f"signal_snapshot:{snapshot.id}"
    excerpt = str(snapshot.signals)[:2000]
    doc = _base_doc(
        chunk_id=chunk_id,
        doc_type="signal_snapshot",
        url=url,
        excerpt=excerpt,
        content={**snapshot.signals, "evidence_hash": snapshot.evidence_hash},
        evidence_hash=snapshot.evidence_hash,
    )
    client.index_document(doc, doc_id=chunk_id)


def index_review_override_doc(override: ReviewOverride, url: Url) -> None:
    client = get_opensearch_client()
    if not client.enabled:
        return
    chunk_id = f"reviewer_note:{override.id}"
    excerpt = (override.notes or override.override_reason)[:2000]
    doc = _base_doc(
        chunk_id=chunk_id,
        doc_type="reviewer_note",
        url=url,
        excerpt=excerpt,
        content={
            "final_label": override.final_label,
            "override_reason": override.override_reason,
            "notes": override.notes,
            "reviewer_id": override.reviewer_id,
        },
        evidence_hash=override.evidence_hash,
        tier=override.final_label,
    )
    client.index_document(doc, doc_id=chunk_id)


async def index_recent_entities(
    session: AsyncSession,
    *,
    limit: int = 50,
) -> int:
    """Backfill index for recent classifications not yet indexed (poll worker)."""
    client = get_opensearch_client()
    if not client.enabled:
        return 0

    client.ensure_index()
    indexed = 0

    rows = (
        await session.execute(
            select(Classification, Url)
            .join(Url, Url.id == Classification.url_id)
            .order_by(Classification.created_at.desc())
            .limit(limit)
        )
    ).all()
    for cls, url in rows:
        index_classification_doc(cls, url)
        indexed += 1

    snapshots = (
        await session.execute(
            select(SignalSnapshot, Url)
            .join(Url, Url.id == SignalSnapshot.url_id)
            .order_by(SignalSnapshot.created_at.desc())
            .limit(limit)
        )
    ).all()
    for snapshot, url in snapshots:
        index_signal_snapshot_doc(snapshot, url)
        indexed += 1

    overrides = (
        await session.execute(
            select(ReviewOverride, Url)
            .join(Url, Url.id == ReviewOverride.url_id)
            .order_by(ReviewOverride.created_at.desc())
            .limit(limit)
        )
    ).all()
    for override, url in overrides:
        index_review_override_doc(override, url)
        indexed += 1

    if indexed:
        logger.info("opensearch_index_batch_complete", documents=indexed)
    return indexed


async def index_url_entities(session: AsyncSession, url_id: uuid.UUID) -> int:
    """Index all RAG-relevant entities for a single URL (event-driven path)."""
    url = await session.get(Url, url_id)
    if url is None:
        return 0

    count = 0
    classifications = (
        await session.execute(
            select(Classification)
            .where(Classification.url_id == url_id)
            .order_by(Classification.created_at.desc())
            .limit(5)
        )
    ).scalars().all()
    for cls in classifications:
        index_classification_doc(cls, url)
        count += 1

    snapshots = (
        await session.execute(
            select(SignalSnapshot)
            .where(SignalSnapshot.url_id == url_id)
            .order_by(SignalSnapshot.version.desc())
            .limit(3)
        )
    ).scalars().all()
    for snapshot in snapshots:
        index_signal_snapshot_doc(snapshot, url)
        count += 1

    overrides = (
        await session.execute(
            select(ReviewOverride)
            .where(ReviewOverride.url_id == url_id)
            .order_by(ReviewOverride.created_at.desc())
            .limit(5)
        )
    ).scalars().all()
    for override in overrides:
        index_review_override_doc(override, url)
        count += 1

    return count
