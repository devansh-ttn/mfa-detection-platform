"""Unit tests for the MFA rules engine."""

import pytest

from mfa_ml.rules.engine import RulesEngine


@pytest.fixture
def engine() -> RulesEngine:
    return RulesEngine()


class TestR1HighAdDensity:
    def test_fires_when_both_conditions_met(self, engine: RulesEngine) -> None:
        match = engine.evaluate({"ad_to_content_ratio": 0.50, "ad_slots_count": 10})
        assert match is not None
        assert match.rule_id == "R1"
        assert match.tier == "MFA_High"
        assert match.mfa_score >= 0.85

    def test_no_fire_low_ratio(self, engine: RulesEngine) -> None:
        assert engine.evaluate({"ad_to_content_ratio": 0.30, "ad_slots_count": 10}) is None

    def test_no_fire_few_slots(self, engine: RulesEngine) -> None:
        assert engine.evaluate({"ad_to_content_ratio": 0.50, "ad_slots_count": 5}) is None

    def test_no_fire_null_features(self, engine: RulesEngine) -> None:
        assert engine.evaluate({"ad_to_content_ratio": None, "ad_slots_count": 10}) is None
        assert engine.evaluate({}) is None


class TestR2AdsAboveFold:
    def test_fires_correctly(self, engine: RulesEngine) -> None:
        match = engine.evaluate({"ads_above_fold": 4, "ad_to_content_ratio": 0.35})
        assert match is not None
        assert match.rule_id == "R2"
        assert match.tier == "MFA_Medium"

    def test_no_fire_low_above_fold(self, engine: RulesEngine) -> None:
        assert engine.evaluate({"ads_above_fold": 2, "ad_to_content_ratio": 0.35}) is None

    def test_no_fire_low_ratio(self, engine: RulesEngine) -> None:
        assert engine.evaluate({"ads_above_fold": 4, "ad_to_content_ratio": 0.20}) is None


class TestR3ThinContent:
    def test_fires_correctly(self, engine: RulesEngine) -> None:
        match = engine.evaluate({"content_word_count": 30, "ad_slots_count": 6})
        assert match is not None
        assert match.rule_id == "R3"
        assert match.tier == "MFA_High"
        assert match.mfa_score >= 0.80

    def test_no_fire_enough_content(self, engine: RulesEngine) -> None:
        assert engine.evaluate({"content_word_count": 100, "ad_slots_count": 6}) is None

    def test_no_fire_few_slots(self, engine: RulesEngine) -> None:
        assert engine.evaluate({"content_word_count": 30, "ad_slots_count": 3}) is None


class TestR4CleanPublisher:
    def test_fires_correctly(self, engine: RulesEngine) -> None:
        match = engine.evaluate({"ad_to_content_ratio": 0.03, "content_word_count": 800})
        assert match is not None
        assert match.rule_id == "R4"
        assert match.tier == "Non_MFA"
        assert match.mfa_score < 0.15

    def test_no_fire_high_ratio(self, engine: RulesEngine) -> None:
        assert engine.evaluate({"ad_to_content_ratio": 0.10, "content_word_count": 800}) is None

    def test_no_fire_low_word_count(self, engine: RulesEngine) -> None:
        assert engine.evaluate({"ad_to_content_ratio": 0.03, "content_word_count": 200}) is None


class TestRulePriority:
    def test_r1_before_r2(self, engine: RulesEngine) -> None:
        """R1 fires when both R1 and R2 conditions are satisfied."""
        match = engine.evaluate(
            {
                "ad_to_content_ratio": 0.50,
                "ad_slots_count": 10,
                "ads_above_fold": 4,
            }
        )
        assert match is not None
        assert match.rule_id == "R1"

    def test_returns_none_for_empty_features(self, engine: RulesEngine) -> None:
        assert engine.evaluate({}) is None

    def test_top_signals_populated(self, engine: RulesEngine) -> None:
        match = engine.evaluate({"ad_to_content_ratio": 0.50, "ad_slots_count": 10})
        assert match is not None
        assert len(match.top_signals) >= 1
        assert all(sig.rank >= 1 for sig in match.top_signals)
