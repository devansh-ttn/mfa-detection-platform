"""Integration tests for audit event reader."""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime

import pytest
from mfa.audit.reader import get_audit_events_for_url
from mfa.audit.writer import write_audit_event
from mfa.db.models import Base, Classification, Url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

pytestmark = pytest.mark.skipif(
    os.getenv("MFA_RUN_INTEGRATION") != "1",
    reason="Set MFA_RUN_INTEGRATION=1 with Postgres running to execute integration tests",
)


@pytest.fixture
async def session_factory():
    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://mfa:mfa@localhost:5432/mfa",
    )
    engine = create_async_engine(database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    yield factory
    await engine.dispose()


@pytest.mark.asyncio
async def test_get_audit_events_for_url_matches_entity_and_payload(session_factory) -> None:
    url_id = uuid.uuid4()
    classification_id = uuid.uuid4()

    async with session_factory() as session:
        session.add(
            Url(
                id=url_id,
                url="https://audit.test/article",
                normalized_url="https://audit.test/article",
                url_hash="hash-audit",
                domain="audit.test",
            )
        )
        session.add(
            Classification(
                id=classification_id,
                url_id=url_id,
                tier="MFA_Medium",
                mfa_score=0.6,
                confidence="medium",
                top_signals=[],
                explanation="test",
                evidence_hash="a" * 64,
                classifier="xgboost",
                schema_version="v1.1",
                created_at=datetime.now(UTC),
            )
        )
        await write_audit_event(
            session,
            entity_type="url",
            entity_id=str(url_id),
            action="url.ingested",
            payload={"url_id": str(url_id)},
        )
        await write_audit_event(
            session,
            entity_type="classification",
            entity_id=str(classification_id),
            action="classification.scored",
            evidence_hash="a" * 64,
            payload={"url_id": str(url_id), "tier": "MFA_Medium"},
        )
        await write_audit_event(
            session,
            entity_type="other",
            entity_id="unrelated",
            action="other.action",
            payload={},
        )
        await session.commit()

    async with session_factory() as session:
        items, total = await get_audit_events_for_url(session, url_id=url_id)

    assert total == 2
    actions = {item.action for item in items}
    assert actions == {"url.ingested", "classification.scored"}
