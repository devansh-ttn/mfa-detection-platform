"""Shared pytest fixtures for crawler Postgres integration tests."""

from __future__ import annotations

import os
import uuid

import pytest
from mfa.db.models import Base, Url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


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
async def seed_url(session_factory):
    async def _seed(*, url: str = "https://example.com/article") -> uuid.UUID:
        url_id = uuid.uuid4()
        async with session_factory() as session:
            session.add(
                Url(
                    id=url_id,
                    url=url,
                    normalized_url=url,
                    url_hash=f"hash-{url_id.hex[:12]}",
                    domain="example.com",
                )
            )
            await session.commit()
        return url_id

    return _seed
