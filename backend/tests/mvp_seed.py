"""Seed helpers for MVP API integration tests."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from mfa.db.models import Classification, Url
from sqlalchemy.ext.asyncio import AsyncSession


async def seed_classification(
    session: AsyncSession,
    *,
    tier: str = "MFA_Medium",
    confidence: str = "medium",
    domain: str = "example.com",
    mfa_score: float = 0.65,
) -> tuple[Url, Classification]:
    """Insert a URL + classification row for integration tests."""
    url_id = uuid.uuid4()
    classification_id = uuid.uuid4()
    url_row = Url(
        id=url_id,
        url=f"https://{domain}/article",
        normalized_url=f"https://{domain}/article",
        url_hash=f"hash-{url_id.hex[:16]}",
        domain=domain,
    )
    classification = Classification(
        id=classification_id,
        url_id=url_id,
        tier=tier,
        mfa_score=mfa_score,
        confidence=confidence,
        top_signals=[{"feature": "ad_to_content_ratio", "value": 0.4, "contribution": 0.3, "rank": 1}],
        explanation=f"Test explanation for {domain}",
        evidence_hash="a" * 64,
        classifier="xgboost",
        schema_version="v1.1",
        created_at=datetime.now(UTC),
    )
    session.add(url_row)
    session.add(classification)
    await session.flush()
    return url_row, classification
