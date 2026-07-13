#!/usr/bin/env python3
"""Insert demo review-queue rows for frontend E2E walkthrough (MVP-4).

Creates URLs + classifications in HITL tiers (MFA_Medium, Uncertain) so
GET /api/v1/reviews/queue returns data without running the full crawl pipeline.

Examples:
  uv run python scripts/seed/seed_reviewer_demo.py
  uv run python scripts/seed/seed_reviewer_demo.py --database-url postgresql+asyncpg://mfa:mfa@localhost:5432/mfa
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend" / "src"))

from mfa.db.models import Classification, Url  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine  # noqa: E402

DEMO_ROWS = [
    {
        "domain": "demo-mfa.example",
        "tier": "MFA_Medium",
        "confidence": "medium",
        "mfa_score": 0.62,
        "explanation": "Elevated ad density and low editorial depth suggest MFA risk.",
    },
    {
        "domain": "demo-uncertain.example",
        "tier": "Uncertain",
        "confidence": "low",
        "mfa_score": 0.48,
        "explanation": "Mixed signals — referral delta and content ratio near decision boundary.",
    },
    {
        "domain": "demo-borderline.example",
        "tier": "MFA_Medium",
        "confidence": "medium",
        "mfa_score": 0.58,
        "explanation": "High refresh cadence with stacked display units above the fold.",
    },
]


async def seed_demo_rows(session: AsyncSession) -> int:
    created = 0
    for row in DEMO_ROWS:
        domain = row["domain"]
        existing = await session.execute(
            Url.__table__.select().where(Url.domain == domain).limit(1)
        )
        if existing.first():
            continue

        url_id = uuid.uuid4()
        classification_id = uuid.uuid4()
        session.add(
            Url(
                id=url_id,
                url=f"https://{domain}/article",
                normalized_url=f"https://{domain}/article",
                url_hash=f"demo-{url_id.hex[:16]}",
                domain=domain,
            )
        )
        session.add(
            Classification(
                id=classification_id,
                url_id=url_id,
                tier=row["tier"],
                mfa_score=row["mfa_score"],
                confidence=row["confidence"],
                top_signals=[
                    {
                        "feature": "ad_to_content_ratio",
                        "value": 0.42,
                        "contribution": 0.28,
                        "rank": 1,
                    }
                ],
                explanation=row["explanation"],
                evidence_hash="d" * 64,
                classifier="demo-seed",
                schema_version="v1.1",
                created_at=datetime.now(UTC),
            )
        )
        created += 1

    await session.commit()
    return created


async def main(database_url: str) -> None:
    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        created = await seed_demo_rows(session)
    await engine.dispose()
    print(f"Seeded {created} demo review-queue row(s). Re-run is idempotent (skips existing domains).")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database-url",
        default=os.getenv(
            "DATABASE_URL",
            "postgresql+asyncpg://mfa:mfa@localhost:5432/mfa",
        ),
        help="Async SQLAlchemy database URL",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(main(args.database_url))
