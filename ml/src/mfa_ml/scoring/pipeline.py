"""Unified scoring pipeline — rules → XGBoost → tier → SHAP → explanation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import structlog

from mfa_ml.data.loader import CRAWL_FEATURE_NAMES
from mfa_ml.scoring.artifact_loader import ScoringArtifacts, load_scoring_artifacts
from mfa_ml.scoring.explanation import render_explanation
from mfa_ml.scoring.output import ClassificationOutput
from mfa_ml.scoring.tier_mapper import calibrated_confidence_from_proba, map_tier

logger = structlog.get_logger(__name__)


def extract_features(signals: dict[str, Any]) -> dict[str, Any]:
    """Pull crawl feature fields from a ``signal_snapshots.signals`` JSONB blob."""
    return {name: signals.get(name) for name in CRAWL_FEATURE_NAMES}


def classify_snapshot(
    signals: dict[str, Any],
    *,
    evidence_hash: str,
    artifacts: ScoringArtifacts | None = None,
    artifact_dir: Path | None = None,
) -> ClassificationOutput:
    """Score a single signal snapshot through the full Baseline pipeline.

    Args:
        signals: Raw JSONB from ``signal_snapshots.signals`` (flat feature dict
            or payload with ``schema_version`` / ``crawl_ts`` metadata).
        evidence_hash: Hash of the evidence pack for audit binding.
        artifacts: Pre-loaded scoring objects (preferred in workers).
        artifact_dir: Load artifacts from disk when *artifacts* is omitted.

    Returns:
        ``ClassificationOutput`` matching the platform output contract.

    Raises:
        ValueError: Neither *artifacts* nor *artifact_dir* was provided.
        FileNotFoundError: *artifact_dir* is missing required files.
    """
    if artifacts is None:
        if artifact_dir is None:
            raise ValueError("Provide artifacts or artifact_dir")
        artifacts = load_scoring_artifacts(artifact_dir)

    features = extract_features(signals)
    rule_match = artifacts.rules_engine.evaluate(features)

    if rule_match is not None:
        return ClassificationOutput(
            tier=rule_match.tier,
            mfa_score=rule_match.mfa_score,
            confidence="high",
            top_signals=rule_match.top_signals,
            explanation=render_explanation(rule_match.tier, rule_match.top_signals),
            evidence_hash=evidence_hash,
            classifier="rules",
            schema_version="v1.1",
        )

    raw_proba = float(artifacts.classifier.predict_proba([features])[0])
    calibrated = float(artifacts.calibrator.transform(np.array([raw_proba]))[0])
    conf_score = calibrated_confidence_from_proba(calibrated)
    tier, conf_label = map_tier(calibrated, conf_score, artifacts.thresholds)
    top_signals = artifacts.shap_explainer.explain(features)
    explanation = render_explanation(tier, top_signals)

    logger.debug(
        "classify_snapshot_xgboost",
        tier=tier,
        mfa_score=round(calibrated, 4),
        confidence=conf_label,
    )

    return ClassificationOutput(
        tier=tier,
        mfa_score=round(calibrated, 4),
        confidence=conf_label,
        top_signals=top_signals,
        explanation=explanation,
        evidence_hash=evidence_hash,
        classifier="xgboost",
        schema_version="v1.1",
    )
