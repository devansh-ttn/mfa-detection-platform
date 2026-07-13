"""Confidence band validation for MVP-2.2."""

from __future__ import annotations

from typing import Any

import numpy as np

from mfa_ml.scoring.tier_mapper import calibrated_confidence_from_proba, map_tier


def confidence_band_report(
    y_true: list[int],
    y_proba: list[float],
) -> dict[str, Any]:
    """Summarize tier/confidence distribution on a holdout set."""
    bands: dict[str, int] = {"high": 0, "medium": 0, "low": 0}
    tiers: dict[str, int] = {}
    for label, proba in zip(y_true, y_proba, strict=True):
        conf_score = calibrated_confidence_from_proba(proba)
        tier, conf_label = map_tier(proba, conf_score)
        bands[conf_label] = bands.get(conf_label, 0) + 1
        tiers[tier] = tiers.get(tier, 0) + 1

    return {
        "n_samples": len(y_true),
        "confidence_bands": bands,
        "tier_distribution": tiers,
        "mean_proba": float(np.mean(y_proba)) if y_proba else 0.0,
    }
