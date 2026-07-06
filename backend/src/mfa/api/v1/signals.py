import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from mfa.core.errors import NotFoundError
from mfa.db.models import SignalSnapshot, Url
from mfa.db.session import get_db_session
from mfa.schemas.signals import SignalSnapshotListResponse, SignalSnapshotResponse

router = APIRouter(tags=["signals"])


@router.get("/signals/{url_id}", response_model=SignalSnapshotListResponse)
async def list_signal_snapshots(
    url_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> SignalSnapshotListResponse:
    url_exists = await session.scalar(select(Url.id).where(Url.id == url_id))
    if url_exists is None:
        raise NotFoundError(f"URL not found: {url_id}", code="url_not_found")

    total = await session.scalar(
        select(func.count()).select_from(SignalSnapshot).where(SignalSnapshot.url_id == url_id)
    )
    total = int(total or 0)

    rows = await session.scalars(
        select(SignalSnapshot)
        .where(SignalSnapshot.url_id == url_id)
        .order_by(SignalSnapshot.version.desc())
        .limit(limit)
        .offset(offset)
    )

    snapshots = [
        SignalSnapshotResponse(
            snapshot_id=row.id,
            url_id=row.url_id,
            version=row.version,
            signals=row.signals,
            evidence_hash=row.evidence_hash,
            persona=row.persona,  # type: ignore[arg-type]
            crawl_duration_sec=row.crawl_duration_sec,
            created_at=row.created_at,
        )
        for row in rows
    ]

    return SignalSnapshotListResponse(
        url_id=url_id,
        snapshots=snapshots,
        total=total,
        limit=limit,
        offset=offset,
    )
