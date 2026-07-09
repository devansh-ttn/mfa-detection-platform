import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from mfa.core.errors import NotFoundError
from mfa.db.models import Classification, Url
from mfa.db.session import get_db_session
from mfa.schemas.classifications import ClassificationListResponse, ClassificationResponse

router = APIRouter(tags=["classifications"])


def _to_response(row: Classification) -> ClassificationResponse:
    return ClassificationResponse(
        classification_id=row.id,
        url_id=row.url_id,
        signal_snapshot_id=row.signal_snapshot_id,
        tier=row.tier,  # type: ignore[arg-type]
        mfa_score=row.mfa_score,
        confidence=row.confidence,  # type: ignore[arg-type]
        top_signals=row.top_signals,
        explanation=row.explanation,
        evidence_hash=row.evidence_hash,
        classifier=row.classifier,
        schema_version=row.schema_version,
        created_at=row.created_at,
    )


@router.get("/classifications/{url_id}", response_model=ClassificationResponse)
async def get_latest_classification(
    url_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> ClassificationResponse:
    """Return the most recent classification for a URL."""
    url_exists = await session.scalar(select(Url.id).where(Url.id == url_id))
    if url_exists is None:
        raise NotFoundError(f"URL not found: {url_id}", code="url_not_found")

    row = await session.scalar(
        select(Classification)
        .where(Classification.url_id == url_id)
        .order_by(Classification.created_at.desc())
        .limit(1)
    )
    if row is None:
        raise NotFoundError(
            f"No classification found for URL: {url_id}",
            code="classification_not_found",
        )

    return _to_response(row)


@router.get("/classifications/{url_id}/history", response_model=ClassificationListResponse)
async def list_classification_history(
    url_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> ClassificationListResponse:
    """Return paginated classification history for a URL."""
    url_exists = await session.scalar(select(Url.id).where(Url.id == url_id))
    if url_exists is None:
        raise NotFoundError(f"URL not found: {url_id}", code="url_not_found")

    total = await session.scalar(
        select(func.count()).select_from(Classification).where(Classification.url_id == url_id)
    )
    total = int(total or 0)

    rows = await session.scalars(
        select(Classification)
        .where(Classification.url_id == url_id)
        .order_by(Classification.created_at.desc())
        .limit(limit)
        .offset(offset)
    )

    return ClassificationListResponse(
        url_id=url_id,
        classifications=[_to_response(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )
