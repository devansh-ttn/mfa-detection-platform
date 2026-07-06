"""Unit tests for the SHAP explainer (XGBoost native pred_contribs)."""

from __future__ import annotations

import numpy as np
import pytest

from mfa_ml.ensemble.classifier import MFAXGBClassifier
from mfa_ml.explainability.shap_explainer import SHAPExplainer

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
        features.append({
            "ad_to_content_ratio": float(rng.uniform(0.3, 0.9)),
            "ads_above_fold": int(rng.integers(2, 8)),
            "ad_slots_count": int(rng.integers(5, 15)),
            "sticky_ad_count": int(rng.integers(0, 3)),
            "content_word_count": int(rng.integers(50, 300)),
        })
        labels.append(1)
    for _ in range(n_non_mfa):
        features.append({
            "ad_to_content_ratio": float(rng.uniform(0.0, 0.1)),
            "ads_above_fold": 0,
            "ad_slots_count": int(rng.integers(0, 3)),
            "sticky_ad_count": 0,
            "content_word_count": int(rng.integers(400, 1500)),
        })
        labels.append(0)
    return features, labels


@pytest.fixture(scope="module")
def explainer() -> SHAPExplainer:
    clf = MFAXGBClassifier(FEATURE_NAMES)
    train_f, train_l = _make_samples(40, 110)
    clf.train(train_f, train_l)
    return SHAPExplainer(clf._model, FEATURE_NAMES)


class TestSHAPExplainer:
    def test_explain_returns_up_to_5_contributions(self, explainer: SHAPExplainer) -> None:
        feat = {"ad_to_content_ratio": 0.5, "ad_slots_count": 8, "content_word_count": 100}
        contribs = explainer.explain(feat)
        assert 1 <= len(contribs) <= 5

    def test_ranks_are_sequential(self, explainer: SHAPExplainer) -> None:
        feat = {n: 0.5 for n in FEATURE_NAMES}
        contribs = explainer.explain(feat)
        ranks = [c.rank for c in contribs]
        assert ranks == list(range(1, len(ranks) + 1))

    def test_contributions_are_floats(self, explainer: SHAPExplainer) -> None:
        feat = {n: 0.5 for n in FEATURE_NAMES}
        for c in explainer.explain(feat):
            assert isinstance(c.contribution, float)

    def test_null_features_handled(self, explainer: SHAPExplainer) -> None:
        feat: dict = {}
        contribs = explainer.explain(feat)
        assert len(contribs) >= 1

    def test_batch_explain(self, explainer: SHAPExplainer) -> None:
        fts = [{n: float(i) * 0.1 for n in FEATURE_NAMES} for i in range(5)]
        results = explainer.explain_batch(fts)
        assert len(results) == 5
        for r in results:
            assert 1 <= len(r) <= 5
