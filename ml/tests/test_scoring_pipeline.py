"""Unit tests for the unified scoring pipeline."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from mfa_ml.calibration.calibrator import IsotonicCalibrator
from mfa_ml.ensemble.classifier import MFAXGBClassifier
from mfa_ml.scoring.artifact_loader import ScoringArtifacts, load_scoring_artifacts
from mfa_ml.scoring.pipeline import classify_snapshot, extract_features
FEATURE_NAMES = [
    "ad_to_content_ratio",
    "ads_above_fold",
    "ad_slots_count",
    "sticky_ad_count",
    "content_word_count",
]


def _make_samples(n_mfa: int, n_non_mfa: int) -> tuple[list[dict], list[int]]:
    rng = np.random.default_rng(0)
    features, labels = [], []
    for _ in range(n_mfa):
        features.append(
            {
                "ad_to_content_ratio": float(rng.uniform(0.3, 0.9)),
                "ads_above_fold": int(rng.integers(2, 8)),
                "ad_slots_count": int(rng.integers(5, 15)),
                "sticky_ad_count": int(rng.integers(0, 3)),
                "content_word_count": int(rng.integers(50, 300)),
            }
        )
        labels.append(1)
    for _ in range(n_non_mfa):
        features.append(
            {
                "ad_to_content_ratio": float(rng.uniform(0.0, 0.1)),
                "ads_above_fold": 0,
                "ad_slots_count": int(rng.integers(0, 3)),
                "sticky_ad_count": 0,
                "content_word_count": int(rng.integers(400, 1500)),
            }
        )
        labels.append(0)
    return features, labels


@pytest.fixture(scope="module")
def artifact_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("artifacts")
    clf = MFAXGBClassifier(FEATURE_NAMES)
    train_f, train_l = _make_samples(40, 110)
    val_f, val_l = _make_samples(10, 30)
    clf.train(train_f, train_l, val_f, val_l)
    clf.save(out)

    raw_val = clf.predict_proba(val_f)
    calibrator = IsotonicCalibrator()
    calibrator.fit(raw_val, np.array(val_l, dtype=np.int32))
    import pickle

    with open(out / "calibrator.pkl", "wb") as f:
        pickle.dump(calibrator, f)
    return out


@pytest.fixture(scope="module")
def artifacts(artifact_dir: Path) -> ScoringArtifacts:
    return load_scoring_artifacts(artifact_dir)


class TestExtractFeatures:
    def test_pulls_crawl_fields_from_flat_signals(self) -> None:
        signals = {
            "schema_version": "v1",
            "crawl_ts": "2026-07-06T00:00:00Z",
            "ad_to_content_ratio": 0.5,
            "ad_slots_count": 4,
        }
        features = extract_features(signals)
        assert features["ad_to_content_ratio"] == 0.5
        assert features["ad_slots_count"] == 4
        assert "schema_version" not in features


class TestClassifySnapshot:
    def test_rule_short_circuit_mfa_high(self, artifacts: ScoringArtifacts) -> None:
        signals = {
            "ad_to_content_ratio": 0.55,
            "ad_slots_count": 10,
            "ads_above_fold": 2,
            "content_word_count": 120,
        }
        result = classify_snapshot(
            signals,
            evidence_hash="abc123",
            artifacts=artifacts,
        )
        assert result.tier == "MFA_High"
        assert result.classifier == "rules"
        assert result.confidence == "high"
        assert len(result.top_signals) >= 1
        assert result.explanation
        assert result.evidence_hash == "abc123"

    def test_xgboost_path_when_no_rule_fires(self, artifacts: ScoringArtifacts) -> None:
        signals = {
            "ad_to_content_ratio": 0.18,
            "ads_above_fold": 1,
            "ad_slots_count": 3,
            "sticky_ad_count": 0,
            "content_word_count": 220,
        }
        result = classify_snapshot(
            signals,
            evidence_hash="def456",
            artifacts=artifacts,
        )
        assert result.classifier == "xgboost"
        assert result.tier in ("MFA_High", "MFA_Medium", "MFA_Low", "Non_MFA", "Uncertain")
        assert 0.0 <= result.mfa_score <= 1.0
        assert result.confidence in ("high", "medium", "low")
        assert 1 <= len(result.top_signals) <= 5
        assert len(result.explanation) > 0

    def test_loads_artifacts_from_dir(self, artifact_dir: Path) -> None:
        signals = {
            "ad_to_content_ratio": 0.18,
            "ads_above_fold": 1,
            "ad_slots_count": 3,
            "content_word_count": 220,
        }
        result = classify_snapshot(
            signals,
            evidence_hash="ghi789",
            artifact_dir=artifact_dir,
        )
        assert result.classifier in ("rules", "xgboost")

    def test_missing_artifact_args_raises(self, artifacts: ScoringArtifacts) -> None:
        with pytest.raises(ValueError, match="artifacts or artifact_dir"):
            classify_snapshot({"ad_to_content_ratio": 0.1}, evidence_hash="x")

    def test_output_contract_fields(self, artifacts: ScoringArtifacts) -> None:
        signals = {"ad_to_content_ratio": 0.02, "content_word_count": 800}
        result = classify_snapshot(signals, evidence_hash="hash", artifacts=artifacts)
        assert result.schema_version == "v1.1"
        assert isinstance(result.mfa_score, float)
