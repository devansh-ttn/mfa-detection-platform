"""Unit tests for tier mapper and calibrated confidence helper."""

import pytest

from mfa_ml.scoring.tier_mapper import (
    TierThresholds,
    calibrated_confidence_from_proba,
    map_tier,
)


class TestCalibratedConfidence:
    def test_certain_mfa(self) -> None:
        assert calibrated_confidence_from_proba(0.9) == pytest.approx(0.8)

    def test_certain_non_mfa(self) -> None:
        assert calibrated_confidence_from_proba(0.1) == pytest.approx(0.8)

    def test_borderline(self) -> None:
        assert calibrated_confidence_from_proba(0.5) == pytest.approx(0.0)

    def test_symmetry(self) -> None:
        assert calibrated_confidence_from_proba(0.7) == pytest.approx(
            calibrated_confidence_from_proba(0.3)
        )


class TestMapTier:
    def test_mfa_high(self) -> None:
        tier, conf = map_tier(0.90, 0.85)
        assert tier == "MFA_High"
        assert conf == "high"

    def test_mfa_medium(self) -> None:
        tier, conf = map_tier(0.60, 0.65)
        assert tier == "MFA_Medium"

    def test_mfa_low(self) -> None:
        tier, conf = map_tier(0.30, 0.65)
        assert tier == "MFA_Low"

    def test_non_mfa(self) -> None:
        tier, conf = map_tier(0.10, 0.80)
        assert tier == "Non_MFA"

    def test_uncertain_when_low_confidence(self) -> None:
        tier, _ = map_tier(0.90, 0.30)
        assert tier == "Uncertain"

    def test_high_score_but_uncertain_confidence(self) -> None:
        tier, _ = map_tier(0.85, 0.40)
        assert tier == "Uncertain"

    def test_custom_thresholds(self) -> None:
        custom = TierThresholds(high_score=0.60, high_confidence=0.60, medium_score=0.30)
        tier, _ = map_tier(0.65, 0.70, custom)
        assert tier == "MFA_High"

    def test_threshold_validation_error(self) -> None:
        bad = TierThresholds(high_score=0.30, medium_score=0.50)
        with pytest.raises(ValueError):
            map_tier(0.8, 0.8, bad)
