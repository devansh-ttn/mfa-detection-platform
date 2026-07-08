"""Tests for classifications API."""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from mfa.db.models import Base, Classification, SignalSnapshot, Url
from mfa.db.session import get_db_session
from mfa.ingestion.queue import InMemoryQueue, set_queue
from mfa.main import app

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
async def client(test_engine):
    session_factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db_session] = override_get_db
    set_queue(InMemoryQueue())

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac, session_factory

    app.dependency_overrides.clear()


async def _seed_classification(session_factory) -> tuple[uuid.UUID, uuid.UUID]:
    url_id = uuid.uuid4()
    classification_id = uuid.uuid4()
    snapshot_id = uuid.uuid4()
    async with session_factory() as session:
        session.add(
            Url(
                id=url_id,
                url="https://example.com/article",
                normalized_url="https://example.com/article",
                url_hash="abc123",
                domain="example.com",
            )
        )
        session.add(
            SignalSnapshot(
                id=snapshot_id,
                url_id=url_id,
                version=1,
                signals={"ad_to_content_ratio": 0.55, "content_word_count": 100},
                evidence_hash="d" * 64,
                persona="direct",
            )
        )
        await session.flush()
        session.add(
            Classification(
                id=classification_id,
                url_id=url_id,
                signal_snapshot_id=snapshot_id,
                tier="MFA_High",
                mfa_score=0.9,
                confidence="high",
                top_signals=[
                    {
                        "feature": "ad_to_content_ratio",
                        "value": 0.55,
                        "contribution": 0.45,
                        "rank": 1,
                    }
                ],
                explanation="High ad density detected.",
                evidence_hash="d" * 64,
                classifier="xgboost",
                schema_version="v1",
                created_at=datetime(2026, 7, 8, 12, 0, 0, tzinfo=UTC),
            )
        )
        await session.commit()
    return url_id, classification_id


@pytest.mark.asyncio
async def test_get_latest_classification(client) -> None:
    ac, session_factory = client
    url_id, classification_id = await _seed_classification(session_factory)

    response = await ac.get(f"/api/v1/classifications/{url_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["classification_id"] == str(classification_id)
    assert body["tier"] == "MFA_High"
    assert body["mfa_score"] == 0.9
    assert body["confidence"] == "high"
    assert body["explanation"] == "High ad density detected."
    assert body["evidence_hash"] == "d" * 64
    assert body["classifier"] == "xgboost"
    assert body["schema_version"] == "v1"
    assert len(body["top_signals"]) == 1


@pytest.mark.asyncio
async def test_get_classification_url_not_found(client) -> None:
    ac, _ = client
    missing = uuid.uuid4()
    response = await ac.get(f"/api/v1/classifications/{missing}")
    assert response.status_code == 404
    assert response.json()["code"] == "url_not_found"


@pytest.mark.asyncio
async def test_get_classification_not_found(client) -> None:
    ac, session_factory = client
    url_id = uuid.uuid4()
    async with session_factory() as session:
        session.add(
            Url(
                id=url_id,
                url="https://example.com",
                normalized_url="https://example.com",
                url_hash="xyz789",
                domain="example.com",
            )
        )
        await session.commit()

    response = await ac.get(f"/api/v1/classifications/{url_id}")
    assert response.status_code == 404
    assert response.json()["code"] == "classification_not_found"


@pytest.mark.asyncio
async def test_list_classification_history(client) -> None:
    ac, session_factory = client
    url_id, _ = await _seed_classification(session_factory)

    response = await ac.get(f"/api/v1/classifications/{url_id}/history")
    assert response.status_code == 200
    body = response.json()
    assert body["url_id"] == str(url_id)
    assert body["total"] == 1
    assert len(body["classifications"]) == 1
