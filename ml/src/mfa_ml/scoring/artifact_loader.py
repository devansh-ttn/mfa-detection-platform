"""Load versioned model artifacts for runtime scoring."""

from __future__ import annotations

import pickle
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from mfa_ml.calibration.calibrator import IsotonicCalibrator
from mfa_ml.ensemble.classifier import MFAXGBClassifier
from mfa_ml.explainability.shap_explainer import SHAPExplainer
from mfa_ml.rules.engine import RulesEngine
from mfa_ml.scoring.tier_mapper import TierThresholds


@dataclass(frozen=True)
class ScoringArtifacts:
    """Bundled objects required for ``classify_snapshot``."""

    classifier: MFAXGBClassifier
    calibrator: IsotonicCalibrator
    rules_engine: RulesEngine
    shap_explainer: SHAPExplainer
    thresholds: TierThresholds


def load_scoring_artifacts(
    artifact_dir: Path,
    *,
    expected_schema_version: str = "v1",
    thresholds: TierThresholds | None = None,
) -> ScoringArtifacts:
    """Load classifier, calibrator, and SHAP explainer from *artifact_dir*.

    Args:
        artifact_dir: Directory containing ``model.pkl``, ``metadata.json``,
            and ``calibrator.pkl`` produced by ``ml/scripts/train.py``.
        expected_schema_version: Reject models trained on a different schema.
        thresholds: Optional tier cut-offs; defaults to ``TierThresholds()``.

    Returns:
        ``ScoringArtifacts`` ready for ``classify_snapshot``.

    Raises:
        FileNotFoundError: Missing artifact files.
        ValueError: Schema version mismatch.
    """
    resolved = artifact_dir.resolve()
    classifier = MFAXGBClassifier.load(resolved, expected_schema_version=expected_schema_version)

    calibrator_path = resolved / "calibrator.pkl"
    if not calibrator_path.is_file():
        raise FileNotFoundError(f"calibrator.pkl not found in {resolved}")

    with open(calibrator_path, "rb") as f:
        calibrator: IsotonicCalibrator = pickle.load(f)

    if not calibrator.is_fit:
        raise ValueError(f"calibrator.pkl in {resolved} is not fit")

    model = classifier._model
    if model is None:
        raise ValueError(f"model.pkl in {resolved} has no trained estimator")

    return ScoringArtifacts(
        classifier=classifier,
        calibrator=calibrator,
        rules_engine=RulesEngine(),
        shap_explainer=SHAPExplainer(model, classifier.feature_names),
        thresholds=thresholds or TierThresholds(),
    )


@lru_cache(maxsize=4)
def load_scoring_artifacts_cached(
    artifact_dir: str,
    expected_schema_version: str = "v1",
) -> ScoringArtifacts:
    """Process-local cache for workers that score many URLs per artifact set."""
    return load_scoring_artifacts(
        Path(artifact_dir),
        expected_schema_version=expected_schema_version,
    )
