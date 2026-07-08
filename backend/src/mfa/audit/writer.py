"""Append-only audit event writer."""

from __future__ import annotations

import uuid
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from mfa.db.models import AuditEvent

logger = structlog.get_logger(__name__)


async def write_audit_event(
    session: AsyncSession,
    *,
    entity_type: str,
    entity_id: str,
    action: str,
    evidence_hash: str | None = None,
    payload: dict[str, Any] | None = None,
    actor_id: str = "system",
) -> AuditEvent:
    """Append an audit event row (no update/delete helpers).

    Fields per ``docs/GUARDRAILS.md``: event_id, entity_type, entity_id,
    action, actor_id, occurred_at, evidence_hash, payload.
    """
    event = AuditEvent(
        event_id=str(uuid.uuid4()),
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        actor_id=actor_id,
        evidence_hash=evidence_hash,
        payload=payload or {},
    )
    session.add(event)
    await session.flush()
    logger.info(
        "audit_event_written",
        event_id=event.event_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
    )
    return event
