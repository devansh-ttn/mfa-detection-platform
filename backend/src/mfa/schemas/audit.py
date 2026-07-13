"""Audit event read schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AuditEventItem(BaseModel):
    event_id: str
    entity_type: str
    entity_id: str
    action: str
    actor_id: str
    occurred_at: datetime
    evidence_hash: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class AuditEventListResponse(BaseModel):
    url_id: uuid.UUID
    items: list[AuditEventItem]
    total: int
    limit: int
    offset: int
