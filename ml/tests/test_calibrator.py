"""Unit tests for the isotonic calibrator."""

import numpy as np
import pytest

from mfa_ml.calibration.calibrator import IsotonicCalibrator


def _calibration_data() -> tuple[np.ndarray, np.ndarray]:
    """Synthetic raw probabilities and labels for calibration."""
    rng = np.random.default_rng(42)
    raw = np.concatenate([rng.uniform(0.6, 1.0, 40), rng.uniform(0.0, 0.4, 80)])
    labels = np.array([1] * 40 + [0] * 80, dtype=np.int32)
    return raw, labels


class TestIsotonicCalibrator:
    def test_fit_transform_range(self) -> None:
        raw, labels = _calibration_data()
        cal = IsotonicCalibrator()
        calibrated = cal.fit_transform(raw, labels)
        assert np.all(calibrated >= 0.0) and np.all(calibrated <= 1.0)

    def test_transform_before_fit_raises(self) -> None:
        cal = IsotonicCalibrator()
        with pytest.raises(RuntimeError):
            cal.transform(np.array([0.5]))

    def test_is_fit_flag(self) -> None:
        cal = IsotonicCalibrator()
        assert not cal.is_fit
        raw, labels = _calibration_data()
        cal.fit(raw, labels)
        assert cal.is_fit

    def test_fit_returns_self(self) -> None:
        raw, labels = _calibration_data()
        cal = IsotonicCalibrator()
        result = cal.fit(raw, labels)
        assert result is cal

    def test_high_raw_proba_stays_high(self) -> None:
        raw, labels = _calibration_data()
        cal = IsotonicCalibrator()
        cal.fit(raw, labels)
        high = cal.transform(np.array([0.95]))
        low = cal.transform(np.array([0.05]))
        assert high[0] > low[0]
