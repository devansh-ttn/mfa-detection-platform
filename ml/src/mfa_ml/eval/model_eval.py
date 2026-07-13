"""Model evaluation on gold labels joined with crawled snapshots."""

from __future__ import annotations

import json
import pickle
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import structlog

from mfa_ml.calibration.calibrator import IsotonicCalibrator
from mfa_ml.data.loader import FeatureExtractor, domain_stratified_split
from mfa_ml.ensemble.classifier import MFAXGBClassifier
from mfa_ml.eval.metrics import build_metrics, empty_eval_metrics, predicted_tier_is_mfa
from mfa_ml.rules.engine import RulesEngine
from mfa_ml.scoring.tier_mapper import (
    TierThresholds,
    calibrated_confidence_from_proba,
    map_tier,
)

logger = structlog.get_logger(__name__)

POC_PRECISION_TARGET = 0.85
POC_RECALL_TARGET = 0.70


def _artifacts_ready(artifact_dir: Path) -> bool:
    resolved = artifact_dir.resolve()
    return (resolved / "model.pkl").is_file() and (resolved / "calibrator.pkl").is_file()


def _count_gold_labels(path: Path) -> int:
    count = 0
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                count += 1
    return count


def evaluate_model(
    db_url: str,
    gold_labels_path: Path,
    artifact_dir: Path,
    *,
    val_fraction: float = 0.20,
    random_seed: int = 42,
    eval_all: bool = False,
) -> dict[str, Any]:
    """Run model evaluation and write metrics.json."""
    logger.info("model_eval_start", artifact_dir=str(artifact_dir), eval_all=eval_all)

    extractor = FeatureExtractor(db_url, gold_labels_path)
    samples = extractor.load()
    if not samples:
        logger.warning("model_eval_skipped", reason="no_crawled_snapshots")
        metrics = empty_eval_metrics(
            eval_mode="model_skipped",
            n_total=_count_gold_labels(gold_labels_path),
            precision_target=POC_PRECISION_TARGET,
            recall_target=POC_RECALL_TARGET,
            skipped_reason="no_crawled_snapshots",
            extra={
                "evaluated_at": datetime.now(UTC).isoformat(),
                "artifact_dir": str(artifact_dir),
                "n_samples_with_snapshots": 0,
            },
        )
        metrics_path = artifact_dir / "metrics.json"
        with metrics_path.open("w", encoding="utf-8") as handle:
            json.dump(metrics, handle, indent=2)
        return metrics

    if not _artifacts_ready(artifact_dir):
        logger.warning("model_eval_skipped", reason="missing_model_artifacts")
        metrics = empty_eval_metrics(
            eval_mode="model_skipped",
            n_total=len(samples),
            precision_target=POC_PRECISION_TARGET,
            recall_target=POC_RECALL_TARGET,
            skipped_reason="missing_model_artifacts",
            extra={
                "evaluated_at": datetime.now(UTC).isoformat(),
                "artifact_dir": str(artifact_dir),
                "n_samples_with_snapshots": len(samples),
            },
        )
        metrics_path = artifact_dir / "metrics.json"
        with metrics_path.open("w", encoding="utf-8") as handle:
            json.dump(metrics, handle, indent=2)
        return metrics

    if eval_all:
        eval_samples = samples
        eval_mode = "model_all_crawled"
    else:
        split = domain_stratified_split(samples, val_fraction, random_seed)
        eval_samples = split.val
        eval_mode = "model_holdout"

    classifier = MFAXGBClassifier.load(artifact_dir)
    with open(artifact_dir / "calibrator.pkl", "rb") as handle:
        calibrator: IsotonicCalibrator = pickle.load(handle)

    engine = RulesEngine()
    thresholds = TierThresholds()

    y_true: list[int] = []
    y_pred: list[int] = []
    tiers: list[str] = []

    for sample in eval_samples:
        rule_match = engine.evaluate(sample.features)
        if rule_match is not None:
            predicted_tier = rule_match.tier
        else:
            raw_proba_arr = classifier.predict_proba([sample.features])
            raw_proba = float(raw_proba_arr[0])
            calibrated = float(calibrator.transform(np.array([raw_proba]))[0])
            confidence = calibrated_confidence_from_proba(calibrated)
            predicted_tier, _ = map_tier(calibrated, confidence, thresholds)

        y_true.append(sample.label)
        tiers.append(predicted_tier)
        y_pred.append(1 if predicted_tier_is_mfa(predicted_tier) else 0)

    metrics = build_metrics(
        y_true=y_true,
        y_pred=y_pred,
        predicted_tiers=tiers,
        n_total=len(samples),
        eval_mode=eval_mode,
        precision_target=POC_PRECISION_TARGET,
        recall_target=POC_RECALL_TARGET,
        extra={
            "evaluated_at": datetime.now(UTC).isoformat(),
            "artifact_dir": str(artifact_dir),
            "n_samples_with_snapshots": len(samples),
        },
    )

    metrics_path = artifact_dir / "metrics.json"
    with metrics_path.open("w", encoding="utf-8") as handle:
        json.dump(metrics, handle, indent=2)

    logger.info(
        "model_eval_done",
        precision=metrics["precision"],
        recall=metrics["recall"],
        meets_targets=metrics["poc_targets"]["meets_targets"],
    )
    return metrics
