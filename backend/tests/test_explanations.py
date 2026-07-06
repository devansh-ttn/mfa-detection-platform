"""Tests for Jinja2 template explanation renderer."""

import pytest
from mfa_ml.scoring.output import SignalContribution

from mfa.scoring.explanations.templates import render_explanation


def _sig(feature: str, value: float, contribution: float, rank: int) -> SignalContribution:
    return SignalContribution(feature=feature, value=value, contribution=contribution, rank=rank)


TIERS = ["MFA_High", "MFA_Medium", "MFA_Low", "Non_MFA", "Uncertain"]

TOP_SIGNALS = [
    _sig("ad_to_content_ratio", 0.55, 0.45, 1),
    _sig("ad_slots_count", 9, 0.30, 2),
]


@pytest.mark.parametrize("tier", TIERS)
def test_render_returns_non_empty_string(tier: str) -> None:
    result = render_explanation(tier, TOP_SIGNALS)
    assert isinstance(result, str)
    assert len(result) > 0


@pytest.mark.parametrize("tier", TIERS)
def test_render_with_empty_signals(tier: str) -> None:
    result = render_explanation(tier, [])
    assert isinstance(result, str)
    assert len(result) > 0


def test_mfa_high_mentions_blocking() -> None:
    result = render_explanation("MFA_High", TOP_SIGNALS)
    assert "block" in result.lower() or "MFA" in result


def test_non_mfa_mentions_legitimate() -> None:
    result = render_explanation("Non_MFA", TOP_SIGNALS)
    assert "legitimate" in result.lower() or "Non_MFA" in result or "no mfa" in result.lower()


def test_uncertain_mentions_review() -> None:
    result = render_explanation("Uncertain", TOP_SIGNALS)
    assert "review" in result.lower() or "HITL" in result or "human" in result.lower()


def test_unknown_tier_returns_fallback() -> None:
    result = render_explanation("UNKNOWN_TIER", TOP_SIGNALS)
    assert "UNKNOWN_TIER" in result


def test_signal_features_appear_in_output() -> None:
    result = render_explanation("MFA_High", TOP_SIGNALS)
    assert "ad_to_content_ratio".replace("_", " ") in result.lower() or "0.55" in result
