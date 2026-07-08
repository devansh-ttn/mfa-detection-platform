"""Unit tests for MFAXGBClassifier."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from mfa_ml.ensemble.classifier import MFAXGBClassifier

FEATURE_NAMES = [
    "ad_to_content_ratio",
    "ads_above_fold",
    "ad_slots_count",
    "sticky_ad_count",
    "content_word_count",
]


def _make_samples(n_mfa: int, n_non_mfa: int) -> tuple[list[dict], list[int]]:
    rng = np.random.default_rng(0)
    features, labels = [], []
    for _ in range(n_mfa):
        features.append(
            {
                "ad_to_content_ratio": float(rng.uniform(0.3, 0.9)),
                "ads_above_fold": int(rng.integers(2, 8)),
                "ad_slots_count": int(rng.integers(5, 15)),
                "sticky_ad_count": int(rng.integers(0, 3)),
                "content_word_count": int(rng.integers(50, 300)),
            }
        )
        labels.append(1)
    for _ in range(n_non_mfa):
        features.append(
            {
                "ad_to_content_ratio": float(rng.uniform(0.0, 0.1)),
                "ads_above_fold": 0,
                "ad_slots_count": int(rng.integers(0, 3)),
                "sticky_ad_count": 0,
                "content_word_count": int(rng.integers(400, 1500)),
            }
        )
        labels.append(0)
    return features, labels


@pytest.fixture
def trained_model() -> MFAXGBClassifier:
    clf = MFAXGBClassifier(FEATURE_NAMES)
    train_f, train_l = _make_samples(40, 110)
    val_f, val_l = _make_samples(10, 30)
    clf.train(train_f, train_l, val_f, val_l)
    return clf


class TestMFAXGBClassifier:
    def test_predict_proba_shape(self, trained_model: MFAXGBClassifier) -> None:
        test_f, _ = _make_samples(5, 5)
        probas = trained_model.predict_proba(test_f)
        assert probas.shape == (10,)

    def test_predict_proba_in_range(self, trained_model: MFAXGBClassifier) -> None:
        test_f, _ = _make_samples(5, 5)
        probas = trained_model.predict_proba(test_f)
        assert np.all(probas >= 0.0) and np.all(probas <= 1.0)

    def test_mfa_proba_higher_than_non_mfa(self, trained_model: MFAXGBClassifier) -> None:
        mfa_f, _ = _make_samples(20, 0)
        non_mfa_f, _ = _make_samples(0, 20)
        mfa_probas = trained_model.predict_proba(mfa_f)
        non_mfa_probas = trained_model.predict_proba(non_mfa_f)
        assert mfa_probas.mean() > non_mfa_probas.mean()

    def test_null_features_handled(self, trained_model: MFAXGBClassifier) -> None:
        feat = [{"ad_to_content_ratio": None, "ad_slots_count": None}]
        probas = trained_model.predict_proba(feat)
        assert probas.shape == (1,)

    def test_raises_before_train(self) -> None:
        clf = MFAXGBClassifier(FEATURE_NAMES)
        with pytest.raises(RuntimeError):
            clf.predict_proba([{}])

    def test_raises_on_single_class_train_set(self) -> None:
        clf = MFAXGBClassifier(FEATURE_NAMES)
        train_f, train_l = _make_samples(10, 0)
        with pytest.raises(ValueError, match="both MFA"):
            clf.train(train_f, train_l)

    def test_feature_importances(self, trained_model: MFAXGBClassifier) -> None:
        importances = trained_model.get_feature_importances()
        assert set(importances.keys()) == set(FEATURE_NAMES)

    def test_save_and_load(self, trained_model: MFAXGBClassifier, tmp_path: Path) -> None:
        trained_model.save(tmp_path)
        assert (tmp_path / "model.pkl").exists()
        assert (tmp_path / "metadata.json").exists()

        loaded = MFAXGBClassifier.load(tmp_path)
        test_f, _ = _make_samples(3, 3)
        original_probas = trained_model.predict_proba(test_f)
        loaded_probas = loaded.predict_proba(test_f)
        np.testing.assert_allclose(original_probas, loaded_probas, rtol=1e-5)

    def test_load_rejects_wrong_schema_version(
        self, trained_model: MFAXGBClassifier, tmp_path: Path
    ) -> None:
        trained_model.save(tmp_path)
        import json
        meta_path = tmp_path / "metadata.json"
        with open(meta_path) as f:
            meta = json.load(f)
        meta["feature_schema_version"] = "v99"
        with open(meta_path, "w") as f:
            json.dump(meta, f)
        with pytest.raises(ValueError, match="v99"):
            MFAXGBClassifier.load(tmp_path)
