"""Classification output contract — tier, score, confidence, signals, explanation."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Tier = Literal["MFA_High", "MFA_Medium", "MFA_Low", "Non_MFA", "Uncertain"]
Confidence = Literal["high", "medium", "low"]

TIERS: list[Tier] = ["MFA_High", "MFA_Medium", "MFA_Low", "Non_MFA", "Uncertain"]


class SignalContribution(BaseModel):
    """Single signal's contribution to the classification (SHAP or rule weight)."""

    feature: str = Field(..., description="SignalFeatures field name")
    value: float | int | bool | None = Field(..., description="Observed feature value")
    contribution: float = Field(
        ..., description="Attribution score (positive = MFA, negative = Non_MFA)"
    )
    rank: int = Field(..., ge=1, le=5, description="Rank by abs(contribution), 1 = highest")


class ClassificationOutput(BaseModel):
    """Full output contract required for every classification.

    This model is the canonical source of truth.  Both the ml-worker and the
    backend API use it; backend wraps it in ClassificationResponse for HTTP.
    """

    tier: Tier
    mfa_score: float = Field(..., ge=0.0, le=1.0)
    confidence: Confidence
    top_signals: list[SignalContribution] = Field(default_factory=list, max_length=5)
    explanation: str = Field(default="")
    evidence_hash: str = Field(default="")

    classifier: Literal["rules", "xgboost", "rules+xgboost"] = Field(
        default="xgboost",
        description="Which component produced the tier decision",
    )
    schema_version: str = Field(default="v1")
