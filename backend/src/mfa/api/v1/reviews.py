"""Review queue and override API (MVP-2.3, MVP-2.5)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from mfa.auth.rbac import Role, require_role
from mfa.core.errors import MFAError, NotFoundError
from mfa.db.session import get_db_session
from mfa.reviews.service import create_review_override, get_review_queue
from mfa.schemas.errors import COMMON_ERROR_RESPONSES
from mfa.schemas.reviews import ReviewOverrideRequest, ReviewOverrideResponse, ReviewQueueResponse

router = APIRouter(tags=["reviews"])


@router.get(
    "/reviews/queue",
    response_model=ReviewQueueResponse,
    responses=COMMON_ERROR_RESPONSES,
)
async def list_review_queue(
    session: AsyncSession = Depends(get_db_session),
    tier: list[str] | None = Query(default=None),
    domain: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _actor: str = Depends(require_role(Role.REVIEWER, Role.ADMIN, Role.AD_OPS, Role.AUDITOR)),
) -> ReviewQueueResponse:
    items, total = await get_review_queue(
        session, tier=tier, domain=domain, limit=limit, offset=offset
    )
    return ReviewQueueResponse(items=items, total=total, limit=limit, offset=offset)


@router.post(
    "/reviews",
    response_model=ReviewOverrideResponse,
    status_code=201,
    responses=COMMON_ERROR_RESPONSES,
)
async def submit_review_override(
    body: ReviewOverrideRequest,
    session: AsyncSession = Depends(get_db_session),
    reviewer_id: str = Depends(require_role(Role.REVIEWER, Role.ADMIN, Role.AD_OPS)),
) -> ReviewOverrideResponse:
    try:
        result = await create_review_override(session, request=body, reviewer_id=reviewer_id)
        await session.commit()
        return result
    except LookupError as exc:
        raise NotFoundError(str(exc)) from exc
    except Exception as exc:
        await session.rollback()
        raise MFAError("review override failed", code="internal_error") from exc
