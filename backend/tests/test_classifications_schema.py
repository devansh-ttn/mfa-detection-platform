"""Tests for ClassificationOutput + ClassificationResponse schemas."""

import uuid
from datetime import UTC, datetime

import pytest
from mfa_ml.scoring.output import SignalContribution

from mfa.schemas.classifications import (
    ClassificationListResponse,
    ClassificationOutput,
    ClassificationResponse,
)


def _make_output(**kwargs) -> ClassificationOutput:
    defaults = dict(
        tier="MFA_High",
        mfa_score=0.88,
        confidence="high",
        top_signals=[
            SignalContribution(
                feature="ad_to_content_ratio",
                value=0.55,
                contribution=0.45,
                rank=1,
            )
        ],
        explanation="High ad density detected.",
        evidence_hash="abc123",
    )
    defaults.update(kwargs)
    return ClassificationOutput(**defaults)


class TestClassificationOutput:
    def test_valid_output(self) -> None:
        out = _make_output()
        assert out.tier == "MFA_High"
        assert 0 <= out.mfa_score <= 1

    def test_invalid_tier(self) -> None:
        with pytest.raises(Exception):
            _make_output(tier="INVALID_TIER")

    def test_score_out_of_range(self) -> None:
        with pytest.raises(Exception):
            _make_output(mfa_score=1.5)

    @pytest.mark.parametrize("tier", ["MFA_High", "MFA_Medium", "MFA_Low", "Non_MFA", "Uncertain"])
    def test_all_tiers_valid(self, tier: str) -> None:
        out = _make_output(tier=tier)
        assert out.tier == tier


class TestClassificationResponse:
    def test_from_output(self) -> None:
        out = _make_output()
        resp = ClassificationResponse.from_output(
            classification_id=uuid.uuid4(),
            url_id=uuid.uuid4(),
            output=out,
            created_at=datetime.now(UTC),
        )
        assert resp.tier == out.tier
        assert resp.mfa_score == out.mfa_score
        assert resp.signal_snapshot_id is None

    def test_from_output_with_snapshot_id(self) -> None:
        out = _make_output()
        snap_id = uuid.uuid4()
        resp = ClassificationResponse.from_output(
            classification_id=uuid.uuid4(),
            url_id=uuid.uuid4(),
            output=out,
            created_at=datetime.now(UTC),
            signal_snapshot_id=snap_id,
        )
        assert resp.signal_snapshot_id == snap_id


class TestClassificationListResponse:
    def test_empty_list(self) -> None:
        resp = ClassificationListResponse(
            url_id=uuid.uuid4(),
            classifications=[],
            total=0,
            limit=20,
            offset=0,
        )
        assert resp.total == 0
