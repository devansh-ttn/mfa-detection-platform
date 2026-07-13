"""Audit trail read API (MVP-4)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from mfa.audit.reader import get_audit_events_for_url
from mfa.auth.rbac import Role, require_role
from mfa.core.errors import NotFoundError
from mfa.db.models import Url
from mfa.db.session import get_db_session
from mfa.schemas.audit import AuditEventListResponse
from mfa.schemas.errors import COMMON_ERROR_RESPONSES
from sqlalchemy import select

router = APIRouter(tags=["audit"])


@router.get(
    "/audit",
    response_model=AuditEventListResponse,
    responses=COMMON_ERROR_RESPONSES,
)
async def list_audit_events_for_url(
    url_id: uuid.UUID = Query(..., description="URL to fetch audit events for"),
    session: AsyncSession = Depends(get_db_session),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _actor: str = Depends(
        require_role(Role.REVIEWER, Role.ADMIN, Role.AD_OPS, Role.AUDITOR),
    ),
) -> AuditEventListResponse:
    url_exists = await session.scalar(select(Url.id).where(Url.id == url_id))
    if url_exists is None:
        raise NotFoundError(f"URL not found: {url_id}", code="url_not_found")

    items, total = await get_audit_events_for_url(
        session, url_id=url_id, limit=limit, offset=offset
    )
    return AuditEventListResponse(
        url_id=url_id,
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )
