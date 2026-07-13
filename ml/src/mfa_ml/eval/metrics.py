"""Shared evaluation metrics for model and live pipeline runs."""

from __future__ import annotations

from typing import Any


def confusion_matrix(y_true: list[int], y_pred: list[int]) -> dict[str, int]:
    tp = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 1)
    fp = sum(1 for t, p in zip(y_true, y_pred) if t == 0 and p == 1)
    fn = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 0)
    tn = sum(1 for t, p in zip(y_true, y_pred) if t == 0 and p == 0)
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn}


def precision_recall_f1(cm: dict[str, int]) -> tuple[float, float, float]:
    tp, fp, fn = cm["tp"], cm["fp"], cm["fn"]
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    return precision, recall, f1


def tier_breakdown(
    gold_binary: list[int],
    predicted_tiers: list[str],
) -> dict[str, dict[str, int]]:
    breakdown: dict[str, dict[str, int]] = {}
    for label, tier in zip(gold_binary, predicted_tiers, strict=True):
        entry = breakdown.setdefault(tier, {"MFA": 0, "Non_MFA": 0})
        entry["MFA" if label == 1 else "Non_MFA"] += 1
    return breakdown


def build_metrics(
    *,
    y_true: list[int],
    y_pred: list[int],
    predicted_tiers: list[str],
    n_total: int,
    eval_mode: str,
    precision_target: float,
    recall_target: float,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cm = confusion_matrix(y_true, y_pred)
    precision, recall, f1 = precision_recall_f1(cm)
    metrics: dict[str, Any] = {
        "eval_mode": eval_mode,
        "n_evaluated": len(y_true),
        "n_total_candidates": n_total,
        "val_distribution": {"MFA": sum(y_true), "Non_MFA": len(y_true) - sum(y_true)},
        "confusion_matrix": cm,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "tier_breakdown": tier_breakdown(y_true, predicted_tiers),
        "poc_targets": {
            "precision_target": precision_target,
            "recall_target": recall_target,
            "precision_met": precision >= precision_target,
            "recall_met": recall >= recall_target,
            "meets_targets": precision >= precision_target and recall >= recall_target,
        },
    }
    if extra:
        metrics.update(extra)
    return metrics


def predicted_tier_is_mfa(tier: str) -> bool:
    return tier in ("MFA_High", "MFA_Medium")


def empty_eval_metrics(
    *,
    eval_mode: str,
    n_total: int,
    precision_target: float,
    recall_target: float,
    skipped_reason: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Metrics payload when evaluation cannot run (no crawls, missing artifacts, etc.)."""
    metrics: dict[str, Any] = {
        "eval_mode": eval_mode,
        "n_evaluated": 0,
        "n_total_candidates": n_total,
        "val_distribution": {"MFA": 0, "Non_MFA": 0},
        "confusion_matrix": {"tp": 0, "fp": 0, "fn": 0, "tn": 0},
        "precision": 0.0,
        "recall": 0.0,
        "f1": 0.0,
        "tier_breakdown": {},
        "skipped_reason": skipped_reason,
        "poc_targets": {
            "precision_target": precision_target,
            "recall_target": recall_target,
            "precision_met": False,
            "recall_met": False,
            "meets_targets": False,
        },
    }
    if extra:
        metrics.update(extra)
    return metrics
