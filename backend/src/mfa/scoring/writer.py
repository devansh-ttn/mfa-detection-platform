"""Persist classification rows from ml-worker output."""

from __future__ import annotations

import uuid

import structlog
from mfa_ml.scoring.output import ClassificationOutput
from sqlalchemy.ext.asyncio import AsyncSession

from mfa.db.models import Classification

logger = structlog.get_logger(__name__)


async def write_classification(
    session: AsyncSession,
    *,
    url_id: uuid.UUID,
    signal_snapshot_id: uuid.UUID,
    output: ClassificationOutput,
) -> Classification:
    """Insert a classification row (append-only)."""
    top_signals = [signal.model_dump(mode="json") for signal in output.top_signals]

    row = Classification(
        url_id=url_id,
        signal_snapshot_id=signal_snapshot_id,
        tier=output.tier,
        mfa_score=output.mfa_score,
        confidence=output.confidence,
        top_signals=top_signals,
        explanation=output.explanation,
        evidence_hash=output.evidence_hash,
        classifier=output.classifier,
        schema_version=output.schema_version,
    )
    session.add(row)
    await session.flush()
    logger.info(
        "classification_written",
        classification_id=str(row.id),
        url_id=str(url_id),
        tier=output.tier,
        classifier=output.classifier,
    )
    return row
