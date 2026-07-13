import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from mfa.core.errors import MFAError, NotFoundError
from mfa.db.models import Classification, Url
from mfa.db.session import get_db_session
from mfa.schemas.classifications import (
    ClassificationIndexItem,
    ClassificationIndexResponse,
    ClassificationListResponse,
    ClassificationResponse,
)
from mfa.schemas.errors import COMMON_ERROR_RESPONSES
from mfa.scoring.classification_list import (
    VALID_CONFIDENCES,
    VALID_TIERS,
    classification_index_stmt,
    latest_classification_ids_stmt,
    parse_confidence_filter,
    parse_tier_filter,
)

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


def _to_index_item(row: Classification, url_row: Url) -> ClassificationIndexItem:
    base = _to_response(row)
    return ClassificationIndexItem(
        **base.model_dump(),
        url=url_row.url,
        domain=url_row.domain,
    )


def _validate_tier_filter(tier: list[str] | None) -> list[str] | None:
    try:
        return parse_tier_filter(tier)
    except ValueError as exc:
        raise MFAError(str(exc), code="validation_error", details={"allowed": sorted(VALID_TIERS)}) from exc


def _validate_confidence_filter(confidence: list[str] | None) -> list[str] | None:
    try:
        return parse_confidence_filter(confidence)
    except ValueError as exc:
        raise MFAError(
            str(exc), code="validation_error", details={"allowed": sorted(VALID_CONFIDENCES)}
        ) from exc


@router.get(
    "/classifications",
    response_model=ClassificationIndexResponse,
    responses=COMMON_ERROR_RESPONSES,
)
async def list_classifications(
    session: AsyncSession = Depends(get_db_session),
    tier: list[str] | None = Query(
        default=None,
        description="Filter by MFA tier (repeat param for multiple values)",
    ),
    domain: str | None = Query(default=None, description="Filter by URL domain"),
    confidence: list[str] | None = Query(
        default=None,
        description="Filter by confidence band (repeat param for multiple values)",
    ),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ClassificationIndexResponse:
    """List latest classification per URL with optional filters."""
    tier = _validate_tier_filter(tier)
    confidence = _validate_confidence_filter(confidence)

    id_stmt = latest_classification_ids_stmt(tier=tier, domain=domain, confidence=confidence)
    total = await session.scalar(select(func.count()).select_from(id_stmt.subquery()))
    total = int(total or 0)

    page_ids = id_stmt.limit(limit).offset(offset)
    rows = await session.execute(classification_index_stmt(page_ids))

    items = [_to_index_item(classification, url_row) for classification, url_row in rows]

    return ClassificationIndexResponse(
        classifications=items,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/classifications/{url_id}",
    response_model=ClassificationResponse,
    responses=COMMON_ERROR_RESPONSES,
)
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


@router.get(
    "/classifications/{url_id}/history",
    response_model=ClassificationListResponse,
    responses=COMMON_ERROR_RESPONSES,
)
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
