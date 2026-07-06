"""Evaluation CLI — precision, recall, confusion matrix on holdout set.

Loads the trained model artifact, runs inference on the validation set
(or a supplied holdout JSONL), and writes metrics to
``ml/artifacts/{version}/metrics.json``.

Usage:
    uv run --package mfa-ml python ml/scripts/evaluate.py \\
        --db-url postgresql://user:pass@localhost:5432/mfadb \\
        --gold-labels data/seed/gold_labels.jsonl \\
        --artifact-dir ml/artifacts/v1

Acceptance criteria (POC-3.7): Precision ≥ 85%, Recall ≥ 70%.

Docs: docs/plans/2026-07-05-phased-build-plan.md (POC-3.7)
"""

from __future__ import annotations

import argparse
import json
import os
import pickle
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import structlog
from mfa_common.logging import configure_logging

from mfa_ml.calibration.calibrator import IsotonicCalibrator
from mfa_ml.data.loader import (
    FeatureExtractor,
    LabeledSample,
    domain_stratified_split,
)
from mfa_ml.ensemble.classifier import MFAXGBClassifier
from mfa_ml.rules.engine import RulesEngine
from mfa_ml.scoring.tier_mapper import (
    TierThresholds,
    calibrated_confidence_from_proba,
    map_tier,
)

logger = structlog.get_logger(__name__)

POC_PRECISION_TARGET = 0.85
POC_RECALL_TARGET = 0.70


def _confusion_matrix(y_true: list[int], y_pred: list[int]) -> dict[str, int]:
    tp = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 1)
    fp = sum(1 for t, p in zip(y_true, y_pred) if t == 0 and p == 1)
    fn = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 0)
    tn = sum(1 for t, p in zip(y_true, y_pred) if t == 0 and p == 0)
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn}


def _precision_recall_f1(cm: dict[str, int]) -> tuple[float, float, float]:
    tp, fp, fn = cm["tp"], cm["fp"], cm["fn"]
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    return precision, recall, f1


def _tier_breakdown(
    samples: list[LabeledSample],
    tiers: list[str],
) -> dict[str, dict[str, int]]:
    """Count actual gold labels per predicted tier."""
    breakdown: dict[str, dict[str, int]] = {}
    for sample, tier in zip(samples, tiers):
        entry = breakdown.setdefault(tier, {"MFA": 0, "Non_MFA": 0})
        entry["MFA" if sample.label == 1 else "Non_MFA"] += 1
    return breakdown


def evaluate(
    db_url: str,
    gold_labels_path: Path,
    artifact_dir: Path,
    val_fraction: float = 0.20,
    random_seed: int = 42,
) -> dict:
    """Run evaluation and write metrics.json.

    Returns the metrics dict for testing / downstream use.
    """
    configure_logging(os.getenv("LOG_LEVEL", "INFO"))
    logger.info("eval_start", artifact_dir=str(artifact_dir))

    extractor = FeatureExtractor(db_url, gold_labels_path)
    samples = extractor.load()

    if not samples:
        logger.error("no_eval_samples")
        sys.exit(1)

    split = domain_stratified_split(samples, val_fraction, random_seed)
    val_samples = split.val

    classifier = MFAXGBClassifier.load(artifact_dir)
    with open(artifact_dir / "calibrator.pkl", "rb") as f:
        calibrator: IsotonicCalibrator = pickle.load(f)

    engine = RulesEngine()
    thresholds = TierThresholds()

    y_true: list[int] = []
    y_pred_binary: list[int] = []
    tiers: list[str] = []

    for sample in val_samples:
        rule_match = engine.evaluate(sample.features)
        if rule_match is not None:
            predicted_tier = rule_match.tier
            raw_proba = rule_match.mfa_score
        else:
            raw_proba_arr = classifier.predict_proba([sample.features])
            raw_proba = float(raw_proba_arr[0])
            calibrated = float(calibrator.transform(np.array([raw_proba]))[0])
            confidence = calibrated_confidence_from_proba(calibrated)
            predicted_tier, _ = map_tier(calibrated, confidence, thresholds)
            raw_proba = calibrated

        y_true.append(sample.label)
        is_mfa_pred = predicted_tier in ("MFA_High", "MFA_Medium")
        y_pred_binary.append(1 if is_mfa_pred else 0)
        tiers.append(predicted_tier)

    cm = _confusion_matrix(y_true, y_pred_binary)
    precision, recall, f1 = _precision_recall_f1(cm)
    tier_breakdown = _tier_breakdown(val_samples, tiers)

    metrics = {
        "evaluated_at": datetime.now(UTC).isoformat(),
        "artifact_dir": str(artifact_dir),
        "n_val": len(val_samples),
        "val_distribution": {"MFA": sum(y_true), "Non_MFA": len(y_true) - sum(y_true)},
        "confusion_matrix": cm,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "tier_breakdown": tier_breakdown,
        "poc_targets": {
            "precision_target": POC_PRECISION_TARGET,
            "recall_target": POC_RECALL_TARGET,
            "precision_met": precision >= POC_PRECISION_TARGET,
            "recall_met": recall >= POC_RECALL_TARGET,
        },
    }

    metrics_path = artifact_dir / "metrics.json"
    with open(metrics_path, "w") as f:
        json.dump(metrics, f, indent=2)

    _print_metrics(metrics)

    targets = metrics["poc_targets"]
    if not targets["precision_met"] or not targets["recall_met"]:
        logger.warning(
            "poc_targets_not_met",
            precision=round(precision, 3),
            recall=round(recall, 3),
            hint="Review feature coverage and re-crawl more gold label URLs.",
        )
    else:
        logger.info("poc_targets_met", precision=round(precision, 3), recall=round(recall, 3))

    return metrics


def _print_metrics(m: dict) -> None:
    print("\n" + "=" * 60)
    print("EVALUATION RESULTS")
    print("=" * 60)
    print(f"Val samples   : {m['n_val']}")
    print(f"Val dist      : {m['val_distribution']}")
    cm = m["confusion_matrix"]
    print(f"Confusion     : TP={cm['tp']} FP={cm['fp']} FN={cm['fn']} TN={cm['tn']}")
    print(f"Precision     : {m['precision']:.1%}  (target ≥ {POC_PRECISION_TARGET:.0%})")
    print(f"Recall        : {m['recall']:.1%}  (target ≥ {POC_RECALL_TARGET:.0%})")
    print(f"F1            : {m['f1']:.1%}")
    tgt = m["poc_targets"]
    status = "PASS" if (tgt["precision_met"] and tgt["recall_met"]) else "FAIL"
    print(f"POC targets   : {status}")
    print("Tier breakdown:")
    for tier, dist in m["tier_breakdown"].items():
        print(f"  {tier:<15} MFA={dist['MFA']}, Non_MFA={dist['Non_MFA']}")
    print("=" * 60)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate MFA classifier on holdout")
    parser.add_argument(
        "--db-url",
        default=os.getenv("DATABASE_URL", "postgresql://mfa:mfa@localhost:5432/mfadb"),
    )
    parser.add_argument(
        "--gold-labels",
        type=Path,
        default=Path("data/seed/gold_labels.jsonl"),
    )
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=Path("ml/artifacts/v1"),
    )
    parser.add_argument("--val-fraction", type=float, default=0.20)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    evaluate(
        db_url=args.db_url,
        gold_labels_path=args.gold_labels,
        artifact_dir=args.artifact_dir,
        val_fraction=args.val_fraction,
        random_seed=args.seed,
    )
