"""Tests for MVP-2.2 confidence band reporting."""

from mfa_ml.eval.confidence_bands import confidence_band_report


def test_confidence_band_report_structure():
    report = confidence_band_report(
        y_true=[1, 0, 1, 0],
        y_proba=[0.9, 0.1, 0.55, 0.45],
    )
    assert report["n_samples"] == 4
    assert "confidence_bands" in report
    assert sum(report["confidence_bands"].values()) == 4
