"""SHAP-based signal attribution using XGBoost's native pred_contribs.

Uses ``model.get_booster().predict(dmatrix, pred_contribs=True)`` which
computes exact TreeSHAP values entirely within XGBoost — no external
``shap`` package required (avoids the numba/llvmlite dependency chain).

Positive SHAP → evidence of MFA.
Negative SHAP → evidence of Non_MFA.

The final column in ``pred_contribs`` is the base value (expected model
output) which is excluded from the feature contributions.

See docs/SIGNALS.md for feature definitions.
TODO(MVP): Migrate to the external ``shap`` library once it drops the hard
numba dependency and supports Python 3.14+.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import xgboost as xgb

from mfa_ml.scoring.output import SignalContribution

SENTINEL_NULL = -1.0
TOP_K = 5


class SHAPExplainer:
    """TreeSHAP explainer using XGBoost's native pred_contribs.

    Args:
        model: Trained ``xgb.XGBClassifier`` instance.
        feature_names: Ordered list of feature names matching the model's
            training columns.
    """

    def __init__(
        self,
        model: xgb.XGBClassifier,
        feature_names: list[str],
    ) -> None:
        self._booster: xgb.Booster = model.get_booster()
        self.feature_names = feature_names

    def _to_dmatrix(self, feature_dict: dict[str, Any]) -> xgb.DMatrix:
        row = np.array(
            [
                SENTINEL_NULL if (v := feature_dict.get(name)) is None else float(v)
                for name in self.feature_names
            ],
            dtype=np.float32,
        ).reshape(1, -1)
        return xgb.DMatrix(row, feature_names=self.feature_names)

    def explain(
        self,
        feature_dict: dict[str, Any],
    ) -> list[SignalContribution]:
        """Return top-5 SHAP contributions for a single URL.

        Args:
            feature_dict: Feature values keyed by name (nulls as ``None``).

        Returns:
            List of up to 5 ``SignalContribution`` objects, ranked 1–5 by
            descending ``|contribution|``.
        """
        dmatrix = self._to_dmatrix(feature_dict)
        contribs_matrix = self._booster.predict(dmatrix, pred_contribs=True)
        values = contribs_matrix[0, :-1]

        indexed = sorted(enumerate(values), key=lambda x: abs(x[1]), reverse=True)
        top_k = indexed[:TOP_K]

        contributions: list[SignalContribution] = []
        for rank, (idx, shap_val) in enumerate(top_k, start=1):
            name = self.feature_names[idx]
            raw_val = feature_dict.get(name)
            contributions.append(
                SignalContribution(
                    feature=name,
                    value=raw_val,
                    contribution=round(float(shap_val), 4),
                    rank=rank,
                )
            )
        return contributions

    def explain_batch(
        self,
        feature_dicts: list[dict[str, Any]],
    ) -> list[list[SignalContribution]]:
        """Explain a batch of URLs.

        Args:
            feature_dicts: List of feature dicts.

        Returns:
            List of top-5 contribution lists, one per input.
        """
        if not feature_dicts:
            return []

        rows = np.array(
            [
                [
                    SENTINEL_NULL if (v := fd.get(name)) is None else float(v)
                    for name in self.feature_names
                ]
                for fd in feature_dicts
            ],
            dtype=np.float32,
        )
        dmatrix = xgb.DMatrix(rows, feature_names=self.feature_names)
        contribs_matrix = self._booster.predict(dmatrix, pred_contribs=True)

        results: list[list[SignalContribution]] = []
        for i, fd in enumerate(feature_dicts):
            values = contribs_matrix[i, :-1]
            indexed = sorted(enumerate(values), key=lambda x: abs(x[1]), reverse=True)
            top_k = indexed[:TOP_K]
            contributions: list[SignalContribution] = []
            for rank, (idx, shap_val) in enumerate(top_k, start=1):
                name = self.feature_names[idx]
                contributions.append(
                    SignalContribution(
                        feature=name,
                        value=fd.get(name),
                        contribution=round(float(shap_val), 4),
                        rank=rank,
                    )
                )
            results.append(contributions)
        return results
