"""Classification API schemas.

``ClassificationOutput`` is the canonical output model defined in
``mfa_ml.scoring.output`` and re-exported here for backend convenience.

``ClassificationResponse`` wraps it with DB metadata for the
``GET /api/v1/classifications/{url_id}`` endpoint (POC-4.5).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from mfa_ml.scoring.output import ClassificationOutput, SignalContribution, Tier
from pydantic import BaseModel, ConfigDict, Field

from mfa.schemas.openapi_examples import (
    CLASSIFICATION_HISTORY_RESPONSE,
    CLASSIFICATION_INDEX_ITEM,
    CLASSIFICATION_INDEX_RESPONSE,
    CLASSIFICATION_RESPONSE,
)

__all__ = [
    "ClassificationOutput",
    "SignalContribution",
    "Tier",
    "ClassificationResponse",
    "ClassificationListResponse",
    "ClassificationIndexItem",
    "ClassificationIndexResponse",
]


class ClassificationResponse(BaseModel):
    """HTTP response shape for a single classification record."""

    model_config = ConfigDict(json_schema_extra={"examples": [CLASSIFICATION_RESPONSE]})

    classification_id: uuid.UUID
    url_id: uuid.UUID
    signal_snapshot_id: uuid.UUID | None
    tier: Tier
    mfa_score: float
    confidence: str
    top_signals: list[SignalContribution]
    explanation: str
    evidence_hash: str
    classifier: str
    schema_version: str
    created_at: datetime

    @classmethod
    def from_output(
        cls,
        classification_id: uuid.UUID,
        url_id: uuid.UUID,
        output: ClassificationOutput,
        created_at: datetime,
        signal_snapshot_id: uuid.UUID | None = None,
    ) -> ClassificationResponse:
        return cls(
            classification_id=classification_id,
            url_id=url_id,
            signal_snapshot_id=signal_snapshot_id,
            tier=output.tier,
            mfa_score=output.mfa_score,
            confidence=output.confidence,
            top_signals=output.top_signals,
            explanation=output.explanation,
            evidence_hash=output.evidence_hash,
            classifier=output.classifier,
            schema_version=output.schema_version,
            created_at=created_at,
        )


class ClassificationListResponse(BaseModel):
    """Paginated classification history for a URL."""

    model_config = ConfigDict(json_schema_extra={"examples": [CLASSIFICATION_HISTORY_RESPONSE]})

    url_id: uuid.UUID
    classifications: list[ClassificationResponse]
    total: int
    limit: int
    offset: int


class ClassificationIndexItem(ClassificationResponse):
    """Classification with URL metadata for list/search endpoints."""

    model_config = ConfigDict(json_schema_extra={"examples": [CLASSIFICATION_INDEX_ITEM]})

    url: str = Field(..., description="Original submitted URL")
    domain: str = Field(..., description="Normalized domain")


class ClassificationIndexResponse(BaseModel):
    """Paginated list of latest classifications across URLs."""

    model_config = ConfigDict(json_schema_extra={"examples": [CLASSIFICATION_INDEX_RESPONSE]})

    classifications: list[ClassificationIndexItem]
    total: int
    limit: int
    offset: int
