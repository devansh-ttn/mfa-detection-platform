"""SHAP-based signal attribution using the external shap library.

Uses ``shap.TreeExplainer`` which calls XGBoost's C++ TreeSHAP kernel
natively — fast, exact, and consistent with ``pred_contribs=True``.

Positive SHAP → evidence of MFA.
Negative SHAP → evidence of Non_MFA.

For binary XGBoost classifiers, ``TreeExplainer.shap_values`` returns:
- shap >= 0.40: single 2-D array, shape (n_samples, n_features)
- shap < 0.40 (legacy): list of two 2-D arrays; index 1 = P(MFA)

Both layouts are handled transparently.

See docs/SIGNALS.md for feature definitions.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import shap
import xgboost as xgb

from mfa_ml.scoring.output import SignalContribution

SENTINEL_NULL = -1.0
TOP_K = 5


class SHAPExplainer:
    """TreeSHAP explainer for MFA XGBoost models.

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
        self._explainer = shap.TreeExplainer(model)
        self.feature_names = feature_names

    def _to_array(self, feature_dict: dict[str, Any]) -> np.ndarray:
        return np.array(
            [
                SENTINEL_NULL if (v := feature_dict.get(name)) is None else float(v)
                for name in self.feature_names
            ],
            dtype=np.float32,
        ).reshape(1, -1)

    def _extract_values(self, shap_output: Any) -> np.ndarray:
        """Normalise shap_values output across library versions.

        Returns a 1-D array of SHAP values for the positive (MFA) class.
        """
        if isinstance(shap_output, list):
            return np.asarray(shap_output[1][0])
        arr = np.asarray(shap_output)
        if arr.ndim == 1:
            return arr
        return arr[0]

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
        X = self._to_array(feature_dict)
        raw = self._explainer.shap_values(X)
        values = self._extract_values(raw)

        indexed = sorted(enumerate(values), key=lambda x: abs(x[1]), reverse=True)
        top_k = indexed[:TOP_K]

        contributions: list[SignalContribution] = []
        for rank, (idx, shap_val) in enumerate(top_k, start=1):
            name = self.feature_names[idx]
            contributions.append(
                SignalContribution(
                    feature=name,
                    value=feature_dict.get(name),
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
        raw = self._explainer.shap_values(rows)

        if isinstance(raw, list):
            all_values = np.asarray(raw[1])
        else:
            all_values = np.asarray(raw)
        if all_values.ndim == 1:
            all_values = all_values.reshape(1, -1)

        results: list[list[SignalContribution]] = []
        for i, fd in enumerate(feature_dicts):
            values = all_values[i]
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
