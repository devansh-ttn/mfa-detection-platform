"""Training pipeline CLI — rules + XGBoost + isotonic calibration.

Loads gold labels + signal_snapshots, performs a domain-level 80/20 split,
runs the rules engine as a pre-filter, trains XGBoost on the remainder,
calibrates probabilities, and saves the model artifact.

Usage:
    uv run --package mfa-ml python ml/scripts/train.py \\
        --db-url postgresql://user:pass@localhost:5432/mfadb \\
        --gold-labels data/seed/gold_labels.jsonl \\
        --artifact-dir ml/artifacts/v1

Docs: docs/plans/2026-07-05-phased-build-plan.md (POC-3.2, POC-3.3)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
import structlog
from mfa_common.logging import configure_logging

from mfa_ml.calibration.calibrator import IsotonicCalibrator
from mfa_ml.data.loader import (
    CRAWL_FEATURE_NAMES,
    DataSplit,
    FeatureExtractor,
    LabeledSample,
    domain_stratified_split,
)
from mfa_ml.ensemble.classifier import MFAXGBClassifier
from mfa_ml.rules.engine import RulesEngine

logger = structlog.get_logger(__name__)

# Features included in the POC training set (5 populated by crawler).
# The remaining CRAWL_FEATURE_NAMES stay null and are handled by sentinel imputation.
TRAINING_FEATURE_NAMES: list[str] = list(CRAWL_FEATURE_NAMES)


def _apply_rules(
    samples: list[LabeledSample],
    engine: RulesEngine,
) -> tuple[list[LabeledSample], list[LabeledSample]]:
    """Partition samples into rule-classified and pass-through for XGBoost.

    Args:
        samples: All labeled samples.
        engine: Configured rules engine.

    Returns:
        (rule_matched, pass_through) — pass_through goes to XGBoost.
    """
    matched: list[LabeledSample] = []
    passthrough: list[LabeledSample] = []
    for s in samples:
        result = engine.evaluate(s.features)
        if result is not None:
            matched.append(s)
        else:
            passthrough.append(s)
    logger.info(
        "rules_prefilter",
        n_matched=len(matched),
        n_passthrough=len(passthrough),
    )
    return matched, passthrough


def _evaluate_rules_accuracy(
    samples: list[LabeledSample],
    engine: RulesEngine,
) -> dict[str, float]:
    """Compute precision/recall of the rules engine on a sample set."""
    tp = fp = fn = tn = 0
    for s in samples:
        result = engine.evaluate(s.features)
        if result is None:
            continue
        predicted_mfa = result.tier in ("MFA_High", "MFA_Medium")
        actual_mfa = s.label == 1
        if predicted_mfa and actual_mfa:
            tp += 1
        elif predicted_mfa and not actual_mfa:
            fp += 1
        elif not predicted_mfa and actual_mfa:
            fn += 1
        else:
            tn += 1

    total = tp + fp + fn + tn
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    return {
        "rule_precision": round(precision, 4),
        "rule_recall": round(recall, 4),
        "rule_coverage": round(total / len(samples), 4) if samples else 0.0,
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
    }


def train(
    db_url: str,
    gold_labels_path: Path,
    artifact_dir: Path,
    val_fraction: float = 0.20,
    random_seed: int = 42,
) -> None:
    """Full training pipeline.

    Steps:
        1. Load feature data and split by domain.
        2. Evaluate rules engine on validation set.
        3. Train XGBoost on rule-pass-through training samples.
        4. Calibrate on validation set.
        5. Save model + calibrator + training summary.
    """
    configure_logging(os.getenv("LOG_LEVEL", "INFO"))

    logger.info("train_start", gold_labels=str(gold_labels_path), artifact_dir=str(artifact_dir))

    extractor = FeatureExtractor(db_url, gold_labels_path)
    samples = extractor.load()

    if not samples:
        logger.error("no_training_samples", hint="Run the crawler on gold label URLs first.")
        sys.exit(1)

    split: DataSplit = domain_stratified_split(samples, val_fraction, random_seed)

    engine = RulesEngine()

    _, train_pass = _apply_rules(split.train, engine)
    rules_metrics = _evaluate_rules_accuracy(split.val, engine)
    logger.info("rules_eval", **rules_metrics)

    if not train_pass:
        logger.warning("all_training_samples_matched_rules_skipping_xgb")
        train_pass = split.train

    classifier = MFAXGBClassifier(
        feature_names=TRAINING_FEATURE_NAMES,
        feature_schema_version="v1",
    )
    train_features = [s.features for s in train_pass]
    train_labels = [s.label for s in train_pass]
    val_features = [s.features for s in split.val]
    val_labels = [s.label for s in split.val]

    classifier.train(train_features, train_labels, val_features, val_labels)

    raw_val_probas = classifier.predict_proba(val_features)
    calibrator = IsotonicCalibrator()
    calibrator.fit(raw_val_probas, np.array(val_labels, dtype=np.int32))

    artifact_dir.mkdir(parents=True, exist_ok=True)
    classifier.save(artifact_dir)

    import pickle
    with open(artifact_dir / "calibrator.pkl", "wb") as f:
        pickle.dump(calibrator, f)

    summary = {
        "n_total_samples": len(samples),
        "n_train": split.n_train,
        "n_val": split.n_val,
        "train_distribution": split.label_distribution("train"),
        "val_distribution": split.label_distribution("val"),
        "rules_metrics": rules_metrics,
        "feature_names": TRAINING_FEATURE_NAMES,
        "artifact_dir": str(artifact_dir),
    }
    with open(artifact_dir / "training_summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    logger.info("train_done", artifact_dir=str(artifact_dir))
    _print_summary(summary)


def _print_summary(summary: dict) -> None:
    print("\n" + "=" * 60)
    print("TRAINING SUMMARY")
    print("=" * 60)
    print(f"Total samples : {summary['n_total_samples']}")
    print(f"Train / Val   : {summary['n_train']} / {summary['n_val']}")
    print(f"Train dist    : {summary['train_distribution']}")
    print(f"Val dist      : {summary['val_distribution']}")
    print(f"Rules coverage: {summary['rules_metrics']['rule_coverage']:.1%}")
    print(f"Rules precision: {summary['rules_metrics']['rule_precision']:.1%}")
    print(f"Rules recall  : {summary['rules_metrics']['rule_recall']:.1%}")
    print(f"Artifacts     : {summary['artifact_dir']}")
    print("=" * 60)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train MFA XGBoost classifier")
    parser.add_argument(
        "--db-url",
        default=os.getenv("DATABASE_URL", "postgresql://mfa:mfa@localhost:5432/mfadb"),
        help="Synchronous Postgres DSN",
    )
    parser.add_argument(
        "--gold-labels",
        type=Path,
        default=Path("data/seed/gold_labels.jsonl"),
        help="Path to gold_labels.jsonl",
    )
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=Path("ml/artifacts/v1"),
        help="Output directory for model artifacts",
    )
    parser.add_argument("--val-fraction", type=float, default=0.20)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    train(
        db_url=args.db_url,
        gold_labels_path=args.gold_labels,
        artifact_dir=args.artifact_dir,
        val_fraction=args.val_fraction,
        random_seed=args.seed,
    )
