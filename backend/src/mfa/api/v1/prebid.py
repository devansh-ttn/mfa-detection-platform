"""Pre-bid domain lookup API (Production PROD-1.2 stub)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from mfa.cache.redis_cache import get_domain_cache
from mfa.db.models import Classification, Url
from mfa.db.session import get_db_session
from mfa.schemas.errors import COMMON_ERROR_RESPONSES

router = APIRouter(tags=["prebid"])


class PrebidLookupResponse(BaseModel):
    domain: str
    tier: str | None
    confidence: str | None
    mfa_score: float | None
    evidence_hash: str | None
    cache_hit: bool
    recommended_action: str


@router.get(
    "/prebid/lookup",
    response_model=PrebidLookupResponse,
    responses=COMMON_ERROR_RESPONSES,
)
async def prebid_domain_lookup(
    domain: str = Query(..., min_length=1, max_length=255),
    session: AsyncSession = Depends(get_db_session),
) -> PrebidLookupResponse:
    cache = get_domain_cache()
    cached = cache.get(domain)
    if cached:
        action = _action_for_tier(cached["tier"])
        return PrebidLookupResponse(
            domain=domain,
            tier=cached["tier"],
            confidence=cached["confidence"],
            mfa_score=cached["mfa_score"],
            evidence_hash=cached["evidence_hash"],
            cache_hit=True,
            recommended_action=action,
        )

    subq = (
        select(Classification.url_id, func.max(Classification.created_at).label("max_created"))
        .join(Url, Url.id == Classification.url_id)
        .where(Url.domain == domain)
        .group_by(Classification.url_id)
        .subquery()
    )
    row = (
        await session.execute(
            select(Classification, Url)
            .join(Url, Url.id == Classification.url_id)
            .join(
                subq,
                (Classification.url_id == subq.c.url_id)
                & (Classification.created_at == subq.c.max_created),
            )
            .where(Url.domain == domain)
            .order_by(Classification.mfa_score.desc())
            .limit(1)
        )
    ).first()

    if row is None:
        return PrebidLookupResponse(
            domain=domain,
            tier=None,
            confidence=None,
            mfa_score=None,
            evidence_hash=None,
            cache_hit=False,
            recommended_action="recheck",
        )

    cls, url_row = row
    cache.set(
        domain,
        tier=cls.tier,
        confidence=cls.confidence,
        mfa_score=cls.mfa_score,
        evidence_hash=cls.evidence_hash,
        url_id=str(url_row.id),
    )
    return PrebidLookupResponse(
        domain=domain,
        tier=cls.tier,
        confidence=cls.confidence,
        mfa_score=cls.mfa_score,
        evidence_hash=cls.evidence_hash,
        cache_hit=False,
        recommended_action=_action_for_tier(cls.tier),
    )


def _action_for_tier(tier: str) -> str:
    if tier == "MFA_High":
        return "block"
    if tier in {"MFA_Medium", "Uncertain"}:
        return "human_review"
    if tier == "MFA_Low":
        return "monitor"
    return "allow"
