"""Blocklist export API (MVP-2.6)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from mfa.config import get_settings
from mfa.db.models import Classification, Url
from mfa.auth.rbac import Role, require_role
from mfa.db.session import get_db_session
from mfa.schemas.errors import COMMON_ERROR_RESPONSES

router = APIRouter(tags=["blocklist"])

DEFAULT_BLOCKLIST_TIERS = ("MFA_High",)


class BlocklistEntry(BaseModel):
    url: str
    domain: str
    tier: str
    mfa_score: float
    confidence: str
    evidence_hash: str


class BlocklistResponse(BaseModel):
    entries: list[BlocklistEntry]
    total: int
    limit: int
    offset: int
    shadow_mode: bool = False


@router.get(
    "/blocklist",
    response_model=BlocklistResponse,
    responses=COMMON_ERROR_RESPONSES,
)
async def export_blocklist(
    session: AsyncSession = Depends(get_db_session),
    tier: list[str] = Query(default=list(DEFAULT_BLOCKLIST_TIERS)),
    confidence: list[str] | None = Query(default=None),
    domain: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    _actor: str = Depends(require_role(Role.AD_OPS, Role.ADMIN, Role.REVIEWER, Role.AUDITOR)),
) -> BlocklistResponse:
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
        .where(Classification.tier.in_(tier))
    )
    if confidence:
        stmt = stmt.where(Classification.confidence.in_(confidence))
    if domain:
        stmt = stmt.where(Url.domain == domain)

    total = int(await session.scalar(select(func.count()).select_from(stmt.subquery())) or 0)
    rows = (
        await session.execute(stmt.order_by(Classification.mfa_score.desc()).limit(limit).offset(offset))
    ).all()

    entries = [
        BlocklistEntry(
            url=url_row.url,
            domain=url_row.domain,
            tier=cls.tier,
            mfa_score=cls.mfa_score,
            confidence=cls.confidence,
            evidence_hash=cls.evidence_hash,
        )
        for cls, url_row in rows
    ]
    return BlocklistResponse(
        entries=entries,
        total=total,
        limit=limit,
        offset=offset,
        shadow_mode=get_settings().mfa_shadow_mode,
    )
