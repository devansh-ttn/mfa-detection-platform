"""HITL review queue and override service."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from mfa.audit.writer import write_audit_event
from mfa.db.models import Classification, ReviewOverride, Url
from mfa.schemas.reviews import ReviewOverrideRequest, ReviewOverrideResponse, ReviewQueueItem

HITL_TIERS = frozenset({"MFA_Medium", "Uncertain"})


async def get_review_queue(
    session: AsyncSession,
    *,
    tier: list[str] | None = None,
    domain: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[ReviewQueueItem], int]:
    tiers = tier or sorted(HITL_TIERS)
    subq = (
        select(Classification.url_id, func.max(Classification.created_at).label("max_created"))
        .group_by(Classification.url_id)
        .subquery()
    )
    stmt = (
        select(Classification, Url)
        .join(Url, Url.id == Classification.url_id)
        .join(
            subq,
            (Classification.url_id == subq.c.url_id)
            & (Classification.created_at == subq.c.max_created),
        )
        .where(Classification.tier.in_(tiers))
    )
    if domain:
        stmt = stmt.where(Url.domain == domain)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = int(await session.scalar(count_stmt) or 0)

    rows = (
        await session.execute(stmt.order_by(Classification.created_at.desc()).limit(limit).offset(offset))
    ).all()

    items = [
        ReviewQueueItem(
            url_id=cls.url_id,
            url=url_row.url,
            domain=url_row.domain,
            classification_id=cls.id,
            tier=cls.tier,
            mfa_score=cls.mfa_score,
            confidence=cls.confidence,
            top_signals=cls.top_signals,
            explanation=cls.explanation,
            evidence_hash=cls.evidence_hash,
            created_at=cls.created_at,
        )
        for cls, url_row in rows
    ]
    return items, total


async def create_review_override(
    session: AsyncSession,
    *,
    request: ReviewOverrideRequest,
    reviewer_id: str,
) -> ReviewOverrideResponse:
    classification = await session.get(Classification, request.classification_id)
    if classification is None:
        raise LookupError(f"classification not found: {request.classification_id}")

    override = ReviewOverride(
        url_id=classification.url_id,
        classification_id=classification.id,
        final_label=request.final_label,
        override_reason=request.override_reason,
        reviewer_id=reviewer_id,
        notes=request.notes,
        ml_tier=classification.tier,
        ml_mfa_score=classification.mfa_score,
        evidence_hash=classification.evidence_hash,
    )
    session.add(override)
    await session.flush()

    await write_audit_event(
        session,
        entity_type="review_override",
        entity_id=str(override.id),
        action="review.override",
        actor_id=reviewer_id,
        evidence_hash=classification.evidence_hash,
        payload={
            "classification_id": str(classification.id),
            "final_label": request.final_label,
            "override_reason": request.override_reason,
            "ml_tier": classification.tier,
        },
    )

    return ReviewOverrideResponse(
        review_id=override.id,
        url_id=override.url_id,
        classification_id=override.classification_id,
        final_label=request.final_label,  # type: ignore[arg-type]
        override_reason=request.override_reason,  # type: ignore[arg-type]
        ml_tier=override.ml_tier,
        ml_mfa_score=override.ml_mfa_score,
        evidence_hash=override.evidence_hash,
        reviewer_id=reviewer_id,
        created_at=override.created_at,
    )
