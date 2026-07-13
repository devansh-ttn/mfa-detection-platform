"""Read audit events for reviewer console."""

from __future__ import annotations

import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from mfa.db.models import AuditEvent, Classification
from mfa.schemas.audit import AuditEventItem


async def get_audit_events_for_url(
    session: AsyncSession,
    *,
    url_id: uuid.UUID,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[AuditEventItem], int]:
    """Return audit events tied to a URL (direct entity or payload linkage)."""
    url_id_str = str(url_id)

    classification_ids = list(
        await session.scalars(select(Classification.id).where(Classification.url_id == url_id))
    )
    classification_id_strs = [str(cid) for cid in classification_ids]

    conditions = [
        (AuditEvent.entity_type == "url") & (AuditEvent.entity_id == url_id_str),
        AuditEvent.payload["url_id"].astext == url_id_str,
    ]
    if classification_id_strs:
        conditions.append(
            (AuditEvent.entity_type == "classification")
            & (AuditEvent.entity_id.in_(classification_id_strs))
        )
        conditions.append(
            (AuditEvent.entity_type == "review_override")
            & (AuditEvent.payload["classification_id"].astext.in_(classification_id_strs))
        )

    stmt = select(AuditEvent).where(or_(*conditions))

    total = int(await session.scalar(select(func.count()).select_from(stmt.subquery())) or 0)
    rows = await session.scalars(
        stmt.order_by(AuditEvent.occurred_at.desc()).limit(limit).offset(offset)
    )

    items = [
        AuditEventItem(
            event_id=row.event_id,
            entity_type=row.entity_type,
            entity_id=row.entity_id,
            action=row.action,
            actor_id=row.actor_id,
            occurred_at=row.occurred_at,
            evidence_hash=row.evidence_hash,
            payload=row.payload,
        )
        for row in rows
    ]
    return items, total
