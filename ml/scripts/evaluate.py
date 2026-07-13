"""Evaluation CLI — precision, recall, confusion matrix on holdout or all crawled samples.

Usage:
    uv run --package mfa-ml python ml/scripts/evaluate.py \\
        --db-url postgresql://mfa:mfa@localhost:5432/mfa \\
        --gold-labels data/seed/gold_labels.jsonl \\
        --artifact-dir ml/artifacts/v1

    # Evaluate all crawled samples (POC-5.4 batch eval)
    uv run --package mfa-ml python ml/scripts/evaluate.py --eval-all
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import structlog
from mfa_common.logging import configure_logging

from mfa_ml.eval.model_eval import POC_PRECISION_TARGET, POC_RECALL_TARGET, evaluate_model
from mfa_ml.eval.pipeline_eval import evaluate_live_pipeline

logger = structlog.get_logger(__name__)


def _print_metrics(m: dict) -> None:
    print("\n" + "=" * 60)
    print("EVALUATION RESULTS")
    print("=" * 60)
    print(f"Mode          : {m.get('eval_mode', 'unknown')}")
    print(f"Evaluated     : {m.get('n_evaluated', m.get('n_val', 0))}")
    print(f"Distribution  : {m.get('val_distribution')}")
    cm = m["confusion_matrix"]
    print(f"Confusion     : TP={cm['tp']} FP={cm['fp']} FN={cm['fn']} TN={cm['tn']}")
    print(f"Precision     : {m['precision']:.1%}  (target ≥ {POC_PRECISION_TARGET:.0%})")
    print(f"Recall        : {m['recall']:.1%}  (target ≥ {POC_RECALL_TARGET:.0%})")
    print(f"F1            : {m['f1']:.1%}")
    tgt = m["poc_targets"]
    status = "PASS" if tgt.get("meets_targets") else "FAIL"
    print(f"POC targets   : {status}")
    print("Tier breakdown:")
    for tier, dist in m["tier_breakdown"].items():
        print(f"  {tier:<15} MFA={dist['MFA']}, Non_MFA={dist['Non_MFA']}")
    print("=" * 60)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate MFA classifier")
    parser.add_argument(
        "--db-url",
        default=os.getenv("DATABASE_URL_SYNC", "postgresql://mfa:mfa@localhost:5432/mfa"),
    )
    parser.add_argument("--gold-labels", type=Path, default=Path("data/seed/gold_labels.jsonl"))
    parser.add_argument("--artifact-dir", type=Path, default=Path("ml/artifacts/v1"))
    parser.add_argument("--val-fraction", type=float, default=0.20)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--eval-all",
        action="store_true",
        help="Evaluate all crawled samples (not holdout split)",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Evaluate stored classifications from DB (live pipeline)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    configure_logging(os.getenv("LOG_LEVEL", "INFO"))

    db_url = args.db_url.replace("postgresql+asyncpg://", "postgresql://").replace(
        "postgresql+psycopg://", "postgresql://"
    )

    if args.live:
        metrics = evaluate_live_pipeline(db_url, args.gold_labels)
    else:
        metrics = evaluate_model(
            db_url=db_url,
            gold_labels_path=args.gold_labels,
            artifact_dir=args.artifact_dir,
            val_fraction=args.val_fraction,
            random_seed=args.seed,
            eval_all=args.eval_all,
        )

    _print_metrics(metrics)
    if not metrics["poc_targets"]["meets_targets"]:
        logger.warning(
            "poc_targets_not_met",
            precision=metrics["precision"],
            recall=metrics["recall"],
        )
        sys.exit(1)
