import os
import uuid
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from mfa.db.models import Base, SignalSnapshot, Url
from mfa.db.session import get_db_session
from mfa.ingestion.queue import InMemoryQueue, set_queue
from mfa.main import app
from mfa.schemas.signals import SignalFeatures, SignalSnapshotPayload, compute_evidence_hash

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
        yield ac

    app.dependency_overrides.clear()


async def _seed_url_with_snapshots(session_factory) -> tuple[uuid.UUID, list[uuid.UUID]]:
    url_id = uuid.uuid4()
    crawl_ts = datetime(2026, 7, 6, 12, 0, 0, tzinfo=UTC)
    snapshot_ids: list[uuid.UUID] = []

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
        for version in (1, 2):
            signals = SignalSnapshotPayload(
                crawl_ts=crawl_ts,
                features=SignalFeatures(
                    ad_to_content_ratio=0.1 * version,
                    content_word_count=100 * version,
                ),
            ).to_db()
            snapshot_id = uuid.uuid4()
            snapshot_ids.append(snapshot_id)
            session.add(
                SignalSnapshot(
                    id=snapshot_id,
                    url_id=url_id,
                    version=version,
                    signals=signals,
                    evidence_hash=compute_evidence_hash(signals),
                    persona="direct",
                    crawl_duration_sec=1.5 * version,
                )
            )
        await session.commit()
    return url_id, snapshot_ids


@pytest.mark.asyncio
async def test_list_signal_snapshots_paginated(client, test_engine) -> None:
    ac = client
    session_factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    url_id, snapshot_ids = await _seed_url_with_snapshots(session_factory)

    response = await ac.get(f"/api/v1/signals/{url_id}?limit=1&offset=0")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert body["limit"] == 1
    assert body["offset"] == 0
    assert len(body["snapshots"]) == 1
    assert body["snapshots"][0]["version"] == 2
    assert body["snapshots"][0]["snapshot_id"] in {str(sid) for sid in snapshot_ids}

    page_two = await ac.get(f"/api/v1/signals/{url_id}?limit=1&offset=1")
    assert page_two.json()["snapshots"][0]["version"] == 1


@pytest.mark.asyncio
async def test_list_signal_snapshots_empty(client) -> None:
    ac = client
    url_id = uuid.uuid4()
    response = await ac.get(f"/api/v1/signals/{url_id}")
    assert response.status_code == 404
    assert response.json()["code"] == "url_not_found"


@pytest.mark.asyncio
async def test_list_signal_snapshots_url_without_snapshots(client, test_engine) -> None:
    ac = client
    url_id = uuid.uuid4()
    session_factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        session.add(
            Url(
                id=url_id,
                url="https://empty.example.com/",
                normalized_url="https://empty.example.com/",
                url_hash="emptyhash",
                domain="empty.example.com",
            )
        )
        await session.commit()

    response = await ac.get(f"/api/v1/signals/{url_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 0
    assert body["snapshots"] == []
