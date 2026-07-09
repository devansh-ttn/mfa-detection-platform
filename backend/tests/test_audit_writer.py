"""Tests for append-only audit writer."""

from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from mfa.audit.writer import write_audit_event
from mfa.db.models import AuditEvent, Base

pytestmark = pytest.mark.skipif(
    os.getenv("MFA_RUN_INTEGRATION") != "1",
    reason="Set MFA_RUN_INTEGRATION=1 with Postgres running to execute integration tests",
)


@pytest.fixture
async def test_engine():
    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://mfa:mfa@localhost:5432/mfa",
    )
    engine = create_async_engine(database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def session_factory(test_engine):
    return async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.mark.asyncio
async def test_write_audit_event_persists_row(session_factory) -> None:
    url_id = str(uuid.uuid4())
    async with session_factory() as session:
        event = await write_audit_event(
            session,
            entity_type="url",
            entity_id=url_id,
            action="url.ingested",
            payload={"job_id": "abc"},
        )
        await session.commit()

    async with session_factory() as session:
        row = await session.scalar(select(AuditEvent).where(AuditEvent.id == event.id))
        assert row is not None
        assert row.entity_type == "url"
        assert row.entity_id == url_id
        assert row.action == "url.ingested"
        assert row.actor_id == "system"
        assert row.payload == {"job_id": "abc"}
        assert row.event_id


@pytest.mark.asyncio
async def test_write_audit_event_with_evidence_hash(session_factory) -> None:
    async with session_factory() as session:
        event = await write_audit_event(
            session,
            entity_type="classification",
            entity_id=str(uuid.uuid4()),
            action="classification.scored",
            evidence_hash="c" * 64,
            payload={"tier": "MFA_High"},
        )
        await session.commit()

    assert event.evidence_hash == "c" * 64
