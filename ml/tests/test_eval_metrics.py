"""Unit tests for shared evaluation metrics."""

from __future__ import annotations

from mfa_ml.eval.metrics import (
    build_metrics,
    confusion_matrix,
    precision_recall_f1,
    predicted_tier_is_mfa,
)


def test_confusion_matrix_basic() -> None:
    cm = confusion_matrix([1, 0, 1, 0], [1, 0, 0, 0])
    assert cm == {"tp": 1, "fp": 0, "fn": 1, "tn": 2}


def test_precision_recall_f1() -> None:
    precision, recall, f1 = precision_recall_f1({"tp": 8, "fp": 2, "fn": 2, "tn": 88})
    assert precision == 0.8
    assert recall == 0.8
    assert round(f1, 3) == 0.8


def test_predicted_tier_is_mfa() -> None:
    assert predicted_tier_is_mfa("MFA_High") is True
    assert predicted_tier_is_mfa("MFA_Medium") is True
    assert predicted_tier_is_mfa("Non_MFA") is False


def test_build_metrics_includes_targets() -> None:
    metrics = build_metrics(
        y_true=[1, 0, 1],
        y_pred=[1, 0, 0],
        predicted_tiers=["MFA_High", "Non_MFA", "Uncertain"],
        n_total=5,
        eval_mode="test",
        precision_target=0.85,
        recall_target=0.70,
    )
    assert metrics["precision"] == 1.0
    assert metrics["recall"] == 0.5
    assert metrics["poc_targets"]["precision_met"] is True
    assert metrics["poc_targets"]["recall_met"] is False
