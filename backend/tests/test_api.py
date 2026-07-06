import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from mfa.db.models import Base
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
    queue = InMemoryQueue()
    set_queue(queue)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac, queue

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_health(client) -> None:
    ac, _ = client
    response = await ac.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_submit_urls_returns_jobs(client) -> None:
    ac, queue = client
    response = await ac.post(
        "/api/v1/urls",
        json={
            "urls": ["https://example.com/page", "https://news.example.org/story"],
            "source_batch_id": "test-batch",
            "priority": 1,
        },
    )
    assert response.status_code == 202
    body = response.json()
    assert body["accepted"] == 2
    assert body["duplicate"] == 0
    assert len(body["jobs"]) == 2
    assert len(queue.messages) == 2

    job_id = body["jobs"][0]["job_id"]
    job_response = await ac.get(f"/api/v1/jobs/{job_id}")
    assert job_response.status_code == 200
    assert job_response.json()["status"] == "queued"


@pytest.mark.asyncio
async def test_submit_urls_idempotent(client) -> None:
    ac, queue = client
    payload = {
        "urls": ["https://duplicate.test/article"],
        "source_batch_id": "dup-batch",
    }
    first = await ac.post("/api/v1/urls", json=payload)
    second = await ac.post("/api/v1/urls", json=payload)

    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json()["accepted"] == 1
    assert second.json()["accepted"] == 0
    assert second.json()["duplicate"] == 1
    assert len(queue.messages) == 1


@pytest.mark.asyncio
async def test_get_job_not_found(client) -> None:
    ac, _ = client
    response = await ac.get(f"/api/v1/jobs/{uuid.uuid4()}")
    assert response.status_code == 404
    assert response.json()["code"] == "job_not_found"
