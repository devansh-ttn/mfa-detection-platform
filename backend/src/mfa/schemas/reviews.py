"""Reviewer override schemas and reason codes."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

OverrideReason = Literal[
    "false_positive_publisher",
    "referral_delta_expected",
    "policy_exception",
    "insufficient_evidence",
    "vendor_disagreement",
    "confirmed_mfa",
    "confirmed_non_mfa",
]

FinalLabel = Literal["MFA_High", "MFA_Medium", "MFA_Low", "Non_MFA", "Uncertain"]


class ReviewOverrideRequest(BaseModel):
    classification_id: uuid.UUID
    final_label: FinalLabel
    override_reason: OverrideReason
    notes: str | None = Field(default=None, max_length=2000)


class ReviewOverrideResponse(BaseModel):
    review_id: uuid.UUID
    url_id: uuid.UUID
    classification_id: uuid.UUID
    final_label: FinalLabel
    override_reason: OverrideReason
    ml_tier: str
    ml_mfa_score: float
    evidence_hash: str
    reviewer_id: str
    created_at: datetime


class ReviewQueueItem(BaseModel):
    url_id: uuid.UUID
    url: str
    domain: str
    classification_id: uuid.UUID
    tier: str
    mfa_score: float
    confidence: str
    top_signals: list
    explanation: str
    evidence_hash: str
    created_at: datetime


class ReviewQueueResponse(BaseModel):
    items: list[ReviewQueueItem]
    total: int
    limit: int
    offset: int
