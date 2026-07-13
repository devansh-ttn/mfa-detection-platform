"""End-to-end integration: score job → ml consumer → classifications API."""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pytest
from httpx import ASGITransport, AsyncClient
from mfa_ml.calibration.calibrator import IsotonicCalibrator
from mfa_ml.ensemble.classifier import MFAXGBClassifier
from mfa_ml.scoring.artifact_loader import load_scoring_artifacts
from mfa_ml.consumer import process_claimed_score_job
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from mfa.db.models import AuditEvent, Base, Classification, ScoreJob, SignalSnapshot, Url
from mfa.db.session import get_db_session
from mfa.ingestion.queue import InMemoryQueue, set_queue
from mfa.ingestion.score_poll import claim_next_score_job, enqueue_score_job
from mfa.main import app

pytestmark = pytest.mark.skipif(
    os.getenv("MFA_RUN_INTEGRATION") != "1",
    reason="Set MFA_RUN_INTEGRATION=1 with Postgres running to execute integration tests",
)

FEATURE_NAMES = [
    "ad_to_content_ratio",
    "ads_above_fold",
    "ad_slots_count",
    "sticky_ad_count",
    "content_word_count",
]


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
def artifacts(tmp_path: Path):
    clf = MFAXGBClassifier(FEATURE_NAMES)
    train_f = [
        {
            "ad_to_content_ratio": 0.8,
            "ads_above_fold": 5,
            "ad_slots_count": 10,
            "sticky_ad_count": 2,
            "content_word_count": 100,
        }
    ] * 20 + [
        {
            "ad_to_content_ratio": 0.05,
            "ads_above_fold": 0,
            "ad_slots_count": 1,
            "sticky_ad_count": 0,
            "content_word_count": 800,
        }
    ] * 20
    train_l = [1] * 20 + [0] * 20
    val_f = train_f[:5]
    val_l = train_l[:5]
    clf.train(train_f, train_l, val_f, val_l)
    clf.save(tmp_path)

    raw_val = clf.predict_proba(val_f)
    calibrator = IsotonicCalibrator()
    calibrator.fit(raw_val, np.array(val_l, dtype=np.int32))
    import pickle

    with open(tmp_path / "calibrator.pkl", "wb") as f:
        pickle.dump(calibrator, f)

    return load_scoring_artifacts(tmp_path)


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


@pytest.mark.asyncio
async def test_score_pipeline_end_to_end(client, artifacts) -> None:
    """Snapshot → score job → ml consumer → classification API + audit."""
    ac, session_factory = client
    url_id = uuid.uuid4()
    snapshot_id = uuid.uuid4()

    async with session_factory() as session:
        session.add(
            Url(
                id=url_id,
                url="https://example.com/article",
                normalized_url="https://example.com/article",
                url_hash=f"hash-{url_id.hex[:12]}",
                domain="example.com",
            )
        )
        session.add(
            SignalSnapshot(
                id=snapshot_id,
                url_id=url_id,
                version=1,
                signals={
                    "schema_version": "v1",
                    "crawl_ts": datetime.now(UTC).isoformat(),
                    "ad_to_content_ratio": 0.8,
                    "ads_above_fold": 5,
                    "ad_slots_count": 10,
                    "sticky_ad_count": 2,
                    "content_word_count": 100,
                },
                evidence_hash="f" * 64,
                persona="direct",
            )
        )
        await enqueue_score_job(session, url_id, snapshot_id)
        await session.commit()

    async with session_factory() as session:
        job = await claim_next_score_job(session)
        assert job is not None
        job_id = job.id
        await session.commit()

    await process_claimed_score_job(
        job_id,
        url_id,
        snapshot_id,
        artifacts=artifacts,
        session_factory=session_factory,
    )

    response = await ac.get(f"/api/v1/classifications/{url_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["url_id"] == str(url_id)
    assert body["tier"] in {"MFA_High", "MFA_Medium", "MFA_Low", "Non_MFA", "Uncertain"}
    assert 0.0 <= body["mfa_score"] <= 1.0
    assert body["confidence"] in {"high", "medium", "low"}
    assert body["explanation"]
    assert body["evidence_hash"] == "f" * 64
    assert body["classifier"]
    assert body["schema_version"] in {"v1", "v1.1"}

    async with session_factory() as session:
        audit = await session.scalar(
            select(AuditEvent).where(AuditEvent.action == "classification.scored")
        )
        assert audit is not None
        assert audit.evidence_hash == "f" * 64

        job = await session.scalar(select(ScoreJob).where(ScoreJob.id == job_id))
        assert job is not None
        assert job.status == "completed"

        classification = await session.scalar(
            select(Classification).where(Classification.url_id == url_id)
        )
        assert classification is not None
