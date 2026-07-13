"""Integration tests for RAG citation validator against the test query set."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from mfa.db.models import Base
from mfa.db.session import get_db_session
from mfa.main import app
from mfa.rag.sanitizer import sanitize_query
from mvp_seed import seed_classification

FIXTURES = Path(__file__).parent / "fixtures" / "rag_query_set.json"

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
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac, session_factory
    app.dependency_overrides.clear()


HEADERS = {"X-MFA-Role": "reviewer", "X-MFA-Actor": "rag-test"}


@pytest.mark.asyncio
async def test_rag_query_set(client):
    ac, session_factory = client
    cases = json.loads(FIXTURES.read_text(encoding="utf-8"))

    async with session_factory() as session:
        await seed_classification(session, tier="MFA_High", domain="rag-grounded.test")
        await session.commit()

    for case in cases:
        query = case["query"]
        if case.get("expect_sanitized"):
            cleaned = sanitize_query(query)
            assert "ignore" not in cleaned.lower() or "[filtered]" in cleaned.lower()
            continue

        domain = case.get("domain")
        resp = await ac.post(
            "/api/v1/chat",
            json={"query": query, "domain": domain},
            headers=HEADERS,
        )
        assert resp.status_code == 200, case["id"]
        data = resp.json()

        if expected := case.get("expect_confidence"):
            assert data["confidence"] == expected, case["id"]
        if expected := case.get("expect_confidence_not"):
            assert data["confidence"] != expected, case["id"]
        if expected := case.get("expect_action"):
            assert data["recommended_action"] == expected, case["id"]
        if prefix := case.get("expect_citation_prefix"):
            assert any(c["id"].startswith(prefix) for c in data["citations"]), case["id"]

        for citation in data["citations"]:
            assert citation["id"]
            assert citation["source"]
