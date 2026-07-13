"""Tests for LLM explanation fallback (MVP-2.4)."""

from mfa.scoring.llm_explanation import generate_llm_explanation


def test_llm_fallback_when_bedrock_disabled(monkeypatch):
    monkeypatch.delenv("BEDROCK_ENABLED", raising=False)
    template = "Template explanation for MFA_High."
    result = generate_llm_explanation(
        tier="MFA_High",
        mfa_score=0.9,
        top_signals=[{"feature": "ad_to_content_ratio", "value": 0.5}],
        signals_snapshot={"ad_to_content_ratio": 0.5},
        template_explanation=template,
    )
    assert result == template
