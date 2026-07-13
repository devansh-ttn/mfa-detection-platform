"""Unit tests for classification list query helpers."""

from __future__ import annotations

import pytest

from mfa.scoring.classification_list import parse_confidence_filter, parse_tier_filter


def test_parse_tier_filter_accepts_comma_separated() -> None:
    assert parse_tier_filter(["MFA_Medium,Uncertain"]) == ["MFA_Medium", "Uncertain"]


def test_parse_tier_filter_accepts_repeated_params() -> None:
    assert parse_tier_filter(["MFA_High", "Non_MFA"]) == ["MFA_High", "Non_MFA"]


def test_parse_tier_filter_rejects_invalid() -> None:
    with pytest.raises(ValueError, match="Invalid tier"):
        parse_tier_filter(["Not_A_Tier"])


def test_parse_confidence_filter_accepts_comma_separated() -> None:
    assert parse_confidence_filter(["high,medium"]) == ["high", "medium"]


def test_parse_confidence_filter_rejects_invalid() -> None:
    with pytest.raises(ValueError, match="Invalid confidence"):
        parse_confidence_filter(["very_high"])
