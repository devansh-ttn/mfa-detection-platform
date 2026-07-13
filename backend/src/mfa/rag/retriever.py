"""Hybrid SQL retriever for RAG v1."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from mfa.db.models import Classification, ReviewOverride, SignalSnapshot, Url
from mfa.rag.opensearch_client import get_opensearch_client
from mfa.rag.schemas import EvidenceChunk


async def retrieve_evidence(
    session: AsyncSession,
    *,
    intent: str,
    query: str,
    url_id: uuid.UUID | None = None,
    domain: str | None = None,
) -> list[EvidenceChunk]:
    chunks: list[EvidenceChunk] = []

    if url_id is None and domain:
        url_row = (
            await session.execute(select(Url).where(Url.domain == domain).limit(1))
        ).scalar_one_or_none()
        if url_row:
            url_id = url_row.id

    if url_id is None:
        return chunks

    url = await session.get(Url, url_id)
    if url is None:
        return chunks

    latest_cls = (
        await session.execute(
            select(Classification)
            .where(Classification.url_id == url_id)
            .order_by(Classification.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    if latest_cls:
        chunks.append(
            EvidenceChunk(
                chunk_id=f"classification:{latest_cls.id}",
                doc_type="classification",
                content={
                    "tier": latest_cls.tier,
                    "mfa_score": latest_cls.mfa_score,
                    "confidence": latest_cls.confidence,
                    "explanation": latest_cls.explanation,
                    "top_signals": latest_cls.top_signals,
                    "evidence_hash": latest_cls.evidence_hash,
                },
                excerpt=latest_cls.explanation[:500],
            )
        )

    snapshot = (
        await session.execute(
            select(SignalSnapshot)
            .where(SignalSnapshot.url_id == url_id)
            .order_by(SignalSnapshot.version.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    if snapshot:
        chunks.append(
            EvidenceChunk(
                chunk_id=f"signal_snapshot:{snapshot.id}",
                doc_type="signal_snapshot",
                content={**snapshot.signals, "evidence_hash": snapshot.evidence_hash},
                excerpt=str(snapshot.signals)[:500],
            )
        )

    if intent == "change_since_review":
        snapshots = (
            await session.execute(
                select(SignalSnapshot)
                .where(SignalSnapshot.url_id == url_id)
                .order_by(SignalSnapshot.version.desc())
                .limit(2)
            )
        ).scalars().all()
        if len(snapshots) == 2:
            newer, older = snapshots[0], snapshots[1]
            diff = _diff_signals(older.signals, newer.signals)
            chunks.append(
                EvidenceChunk(
                    chunk_id=f"snapshot_diff:{older.id}:{newer.id}",
                    doc_type="audit",
                    content=diff,
                    excerpt=str(diff)[:500],
                )
            )

    if intent in {"non_mfa_evidence", "explain_classification"}:
        overrides = (
            await session.execute(
                select(ReviewOverride)
                .where(ReviewOverride.url_id == url_id)
                .order_by(ReviewOverride.created_at.desc())
                .limit(3)
            )
        ).scalars().all()
        for ov in overrides:
            chunks.append(
                EvidenceChunk(
                    chunk_id=f"reviewer_note:{ov.id}",
                    doc_type="reviewer_note",
                    content={
                        "final_label": ov.final_label,
                        "override_reason": ov.override_reason,
                        "notes": ov.notes,
                    },
                    excerpt=(ov.notes or ov.override_reason)[:500],
                )
            )

    # Hybrid vector/BM25 supplement when SQL evidence is thin or query is semantic.
    if len(chunks) < 3 and query.strip():
        os_client = get_opensearch_client()
        filters: dict[str, Any] = {"url_id": str(url_id)}
        if domain:
            filters["domain"] = domain
        vector_hits = os_client.search(query, filters=filters, k=5)
        seen = {c.chunk_id for c in chunks}
        for hit in vector_hits:
            if hit.chunk_id not in seen:
                chunks.append(hit)
                seen.add(hit.chunk_id)

    return chunks


def _diff_signals(old: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    changed: dict[str, Any] = {}
    keys = set(old) | set(new)
    for key in keys:
        if old.get(key) != new.get(key):
            changed[key] = {"old": old.get(key), "new": new.get(key)}
    return changed
