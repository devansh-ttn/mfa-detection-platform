"""Map (mfa_score, calibrated_confidence) → Tier + Confidence label.

Thresholds are configurable and documented in docs/DOMAIN.md.
Default thresholds calibrated for 5-feature POC with binary gold labels.
"""

from __future__ import annotations

from dataclasses import dataclass

from mfa_ml.scoring.output import Confidence, Tier


@dataclass(frozen=True)
class TierThresholds:
    """Score/confidence cut-offs for tier assignment.

    MVP-2.2 recalibration: raised high_score/high_confidence to reduce
    MFA_High false positives observed in POC-5.4 batch eval.
    """

    high_score: float = 0.88
    high_confidence: float = 0.82
    medium_score: float = 0.50
    low_score: float = 0.25
    uncertain_confidence: float = 0.55

    def validate(self) -> None:
        if not (self.high_score > self.medium_score > self.low_score >= 0):
            raise ValueError("Tier thresholds must be strictly descending and ≥ 0")
        if not (0 < self.uncertain_confidence < 1):
            raise ValueError("uncertain_confidence must be in (0, 1)")


DEFAULT_THRESHOLDS = TierThresholds()


def map_tier(
    mfa_score: float,
    calibrated_confidence: float,
    thresholds: TierThresholds = DEFAULT_THRESHOLDS,
) -> tuple[Tier, Confidence]:
    """Return (tier, confidence_label) for a calibrated score.

    Low calibrated confidence always overrides the tier to ``Uncertain``
    (flagged for HITL review) regardless of the raw score.

    Args:
        mfa_score: Calibrated probability of MFA (0–1).
        calibrated_confidence: Absolute distance from 0.5 rescaled to [0, 1].
            High = model is certain; low = borderline prediction.
        thresholds: Override defaults for experiments or threshold tuning.

    Returns:
        Tuple of (Tier, Confidence) matching the output contract.
    """
    thresholds.validate()

    conf_label: Confidence
    if calibrated_confidence >= 0.75:
        conf_label = "high"
    elif calibrated_confidence >= 0.50:
        conf_label = "medium"
    else:
        conf_label = "low"

    if calibrated_confidence < thresholds.uncertain_confidence:
        return "Uncertain", conf_label

    tier: Tier
    if mfa_score >= thresholds.high_score and calibrated_confidence >= thresholds.high_confidence:
        tier = "MFA_High"
    elif mfa_score >= thresholds.medium_score:
        tier = "MFA_Medium"
    elif mfa_score >= thresholds.low_score:
        tier = "MFA_Low"
    else:
        tier = "Non_MFA"

    return tier, conf_label


def calibrated_confidence_from_proba(proba_mfa: float) -> float:
    """Derive a [0,1] confidence score from a calibrated probability.

    Confidence is highest when the model is certain (proba near 0 or 1)
    and lowest when it is borderline (proba near 0.5).

    Args:
        proba_mfa: Calibrated P(MFA) in [0, 1].

    Returns:
        Confidence score in [0, 1].
    """
    return 2.0 * abs(proba_mfa - 0.5)
