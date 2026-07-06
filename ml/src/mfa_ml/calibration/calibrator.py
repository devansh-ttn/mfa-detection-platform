"""Probability calibrator wrapping sklearn's isotonic regression.

Wraps ``sklearn.calibration.CalibratedClassifierCV`` with ``cv='prefit'``
so it calibrates an already-trained XGBoost model on a held-out validation
set.  Isotonic regression is preferred over Platt scaling for XGBoost
because the model already outputs well-ordered scores; isotonic regression
shapes the bins without assuming a parametric form.

Usage:
    calibrator = IsotonicCalibrator()
    calibrator.fit(raw_probas, val_labels)
    calibrated = calibrator.transform(test_probas)
"""

from __future__ import annotations

import numpy as np
from sklearn.isotonic import IsotonicRegression


class IsotonicCalibrator:
    """Post-hoc isotonic calibrator for pre-trained binary classifiers.

    Fits on (raw_proba, true_label) pairs from the validation set and
    transforms raw probabilities from the test set into calibrated ones.
    """

    def __init__(self) -> None:
        self._iso: IsotonicRegression | None = None

    def fit(self, raw_probas: np.ndarray, labels: np.ndarray) -> IsotonicCalibrator:
        """Fit on validation-set (raw_proba, label) pairs.

        Args:
            raw_probas: 1-D array of raw P(MFA) from XGBoost, shape (n,).
            labels: Binary labels (1=MFA, 0=Non_MFA), shape (n,).

        Returns:
            ``self`` for method chaining.
        """
        self._iso = IsotonicRegression(out_of_bounds="clip")
        self._iso.fit(raw_probas, labels)
        return self

    def transform(self, raw_probas: np.ndarray) -> np.ndarray:
        """Map raw probabilities to calibrated ones.

        Args:
            raw_probas: 1-D array of raw P(MFA), shape (n,).

        Returns:
            1-D array of calibrated P(MFA) in [0, 1].

        Raises:
            RuntimeError: If ``fit`` has not been called.
        """
        if self._iso is None:
            raise RuntimeError("Calibrator has not been fit; call fit() first.")
        return self._iso.transform(raw_probas.astype(np.float64))

    def fit_transform(self, raw_probas: np.ndarray, labels: np.ndarray) -> np.ndarray:
        """Fit and transform in one step (uses same data — only for dev)."""
        return self.fit(raw_probas, labels).transform(raw_probas)

    @property
    def is_fit(self) -> bool:
        return self._iso is not None
