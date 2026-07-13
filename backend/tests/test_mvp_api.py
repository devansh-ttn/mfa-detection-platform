"""Tests for review queue, blocklist, prebid, and chat API."""

import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from mfa.db.models import AuditEvent, Base, ReviewOverride
from mfa.audit.writer import write_audit_event
from mfa.db.session import get_db_session
from mfa.main import app
from mvp_seed import seed_classification

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


@pytest.fixture
async def client(session_factory):
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


REVIEWER_HEADERS = {"X-MFA-Role": "reviewer", "X-MFA-Actor": "test-reviewer"}


@pytest.mark.asyncio
async def test_review_queue_empty(client):
    ac, _ = client
    resp = await ac.get("/api/v1/reviews/queue", headers=REVIEWER_HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_review_queue_hitl_tiers(client):
    ac, session_factory = client
    async with session_factory() as session:
        await seed_classification(session, tier="MFA_Medium", domain="hitl-medium.test")
        await seed_classification(session, tier="MFA_High", domain="not-queued.test")
        await session.commit()

    resp = await ac.get("/api/v1/reviews/queue", headers=REVIEWER_HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["tier"] == "MFA_Medium"
    assert data["items"][0]["domain"] == "hitl-medium.test"


@pytest.mark.asyncio
async def test_blocklist_endpoint(client):
    ac, session_factory = client
    async with session_factory() as session:
        await seed_classification(session, tier="MFA_High", domain="blocklist.test", mfa_score=0.92)
        await session.commit()

    resp = await ac.get(
        "/api/v1/blocklist",
        params={"tier": "MFA_High"},
        headers=REVIEWER_HEADERS,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1
    assert any(e["domain"] == "blocklist.test" for e in body["entries"])


@pytest.mark.asyncio
async def test_prebid_lookup_unknown_domain(client):
    ac, _ = client
    resp = await ac.get("/api/v1/prebid/lookup", params={"domain": "unknown-example.test"})
    assert resp.status_code == 200
    assert resp.json()["recommended_action"] == "recheck"


@pytest.mark.asyncio
async def test_chat_insufficient_evidence(client):
    ac, _ = client
    resp = await ac.post(
        "/api/v1/chat",
        json={"query": "Why is example.com marked MFA?", "domain": "nonexistent-domain.test"},
        headers=REVIEWER_HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["confidence"] in {"insufficient", "low", "medium", "high"}
    assert "recommended_action" in data


@pytest.mark.asyncio
async def test_chat_grounded_with_classification(client):
    ac, session_factory = client
    async with session_factory() as session:
        url_row, cls = await seed_classification(session, tier="MFA_High", domain="rag-grounded.test")
        await session.commit()

    resp = await ac.post(
        "/api/v1/chat",
        json={
            "query": "Why is this domain marked MFA?",
            "domain": "rag-grounded.test",
            "url_id": str(url_row.id),
        },
        headers=REVIEWER_HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["confidence"] != "insufficient"
    assert len(data["citations"]) >= 1
    citation_ids = {c["id"] for c in data["citations"]}
    assert f"classification:{cls.id}" in citation_ids


@pytest.mark.asyncio
async def test_review_override_not_found(client):
    ac, _ = client
    fake_id = str(uuid.uuid4())
    resp = await ac.post(
        "/api/v1/reviews",
        json={
            "classification_id": fake_id,
            "final_label": "Non_MFA",
            "override_reason": "false_positive_publisher",
        },
        headers=REVIEWER_HEADERS,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_review_override_e2e_preserves_ml_score(client):
    ac, session_factory = client
    async with session_factory() as session:
        _, classification = await seed_classification(
            session,
            tier="MFA_Medium",
            mfa_score=0.68,
            domain="override-e2e.test",
        )
        classification_id = str(classification.id)
        await session.commit()

    resp = await ac.post(
        "/api/v1/reviews",
        json={
            "classification_id": classification_id,
            "final_label": "Non_MFA",
            "override_reason": "false_positive_publisher",
            "notes": "integration test",
        },
        headers=REVIEWER_HEADERS,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["ml_tier"] == "MFA_Medium"
    assert body["ml_mfa_score"] == 0.68
    assert body["final_label"] == "Non_MFA"

    async with session_factory() as session:
        override = await session.scalar(
            select(ReviewOverride).where(ReviewOverride.classification_id == classification.id)
        )
        assert override is not None
        assert override.ml_tier == "MFA_Medium"
        assert override.ml_mfa_score == 0.68

        audit = await session.scalar(
            select(AuditEvent).where(AuditEvent.action == "review.override")
        )
        assert audit is not None
        assert audit.evidence_hash == classification.evidence_hash


@pytest.mark.asyncio
async def test_rbac_rejects_missing_role_when_strict(client, monkeypatch):
    ac, _ = client
    monkeypatch.setenv("MFA_REQUIRE_AUTH", "1")
    resp = await ac.post(
        "/api/v1/reviews",
        json={
            "classification_id": str(uuid.uuid4()),
            "final_label": "Non_MFA",
            "override_reason": "false_positive_publisher",
        },
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_audit_events_for_url(client):
    ac, session_factory = client
    async with session_factory() as session:
        url_row, classification = await seed_classification(
            session, tier="MFA_Medium", domain="audit-api.test"
        )
        await write_audit_event(
            session,
            entity_type="classification",
            entity_id=str(classification.id),
            action="classification.scored",
            evidence_hash=classification.evidence_hash,
            payload={"url_id": str(url_row.id), "tier": "MFA_Medium"},
        )
        await session.commit()
        url_id = url_row.id

    resp = await ac.get(
        f"/api/v1/audit?url_id={url_id}",
        headers=REVIEWER_HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert any(item["action"] == "classification.scored" for item in data["items"])


@pytest.mark.asyncio
async def test_evidence_artifact_list_empty_without_files(client):
    ac, session_factory = client
    async with session_factory() as session:
        url_row, _ = await seed_classification(session, domain="evidence-api.test")
        await session.commit()
        url_id = url_row.id

    resp = await ac.get(
        f"/api/v1/urls/{url_id}/evidence",
        headers=REVIEWER_HEADERS,
    )
    assert resp.status_code == 200
    assert resp.json()["artifacts"] == []

