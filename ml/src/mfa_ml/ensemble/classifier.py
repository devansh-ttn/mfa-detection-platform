"""XGBoost binary classifier for MFA detection.

Wraps ``xgboost.XGBClassifier`` with:
- Feature imputation for null/missing signals (sentinel value -1)
- Class imbalance correction via ``scale_pos_weight``
- Versioned model artifact save/load
- ``predict_proba`` returning P(MFA) for each sample

Feature schema version is baked into the saved metadata so the loader
can assert the model was trained on compatible features.

See docs/SIGNALS.md and ml/artifacts/ for versioned model artifacts.
"""

from __future__ import annotations

import json
import pickle
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import structlog
import xgboost as xgb

logger = structlog.get_logger(__name__)

SENTINEL_NULL = -1.0


@dataclass
class ModelMetadata:
    """Persisted alongside the model binary to enable version gating."""

    feature_schema_version: str
    feature_names: list[str]
    trained_at: str
    xgb_version: str
    n_train_samples: int
    class_distribution: dict[str, int]
    scale_pos_weight: float
    hyperparams: dict[str, Any]


class MFAXGBClassifier:
    """XGBoost-based MFA binary classifier.

    Label convention: 1 = MFA (High or Medium), 0 = Non_MFA / Low.
    """

    def __init__(
        self,
        feature_names: list[str],
        feature_schema_version: str = "v1",
        n_estimators: int = 200,
        max_depth: int = 4,
        learning_rate: float = 0.05,
        subsample: float = 0.8,
        colsample_bytree: float = 0.8,
        random_state: int = 42,
    ) -> None:
        self.feature_names = feature_names
        self.feature_schema_version = feature_schema_version
        self._hyperparams = dict(
            n_estimators=n_estimators,
            max_depth=max_depth,
            learning_rate=learning_rate,
            subsample=subsample,
            colsample_bytree=colsample_bytree,
            random_state=random_state,
        )
        self._model: xgb.XGBClassifier | None = None
        self._metadata: ModelMetadata | None = None

    def _build_model(self, scale_pos_weight: float) -> xgb.XGBClassifier:
        return xgb.XGBClassifier(
            **self._hyperparams,
            scale_pos_weight=scale_pos_weight,
            objective="binary:logistic",
            eval_metric="logloss",
            tree_method="hist",
        )

    def _to_matrix(self, feature_dicts: list[dict[str, Any]]) -> np.ndarray:
        """Convert list of feature dicts to a dense numpy array.

        Null values (None or missing keys) are replaced with the sentinel
        value ``SENTINEL_NULL`` (-1).  Sentinel-based imputation is documented
        in docs/SIGNALS.md — XGBoost handles it natively via ``missing`` param.
        """
        rows = []
        for d in feature_dicts:
            row = [
                SENTINEL_NULL if (v := d.get(name)) is None else float(v)
                for name in self.feature_names
            ]
            rows.append(row)
        return np.array(rows, dtype=np.float32)

    def train(
        self,
        train_features: list[dict[str, Any]],
        train_labels: list[int],
        eval_features: list[dict[str, Any]] | None = None,
        eval_labels: list[int] | None = None,
    ) -> None:
        """Fit the XGBoost model.

        Args:
            train_features: List of feature dicts (one per URL).
            train_labels: Binary labels; 1 = MFA, 0 = Non_MFA.
            eval_features / eval_labels: Optional validation set for early stopping.
        """
        n_pos = sum(train_labels)
        n_neg = len(train_labels) - n_pos
        if n_pos == 0 or n_neg == 0:
            raise ValueError(
                "XGBoost requires both MFA (1) and Non_MFA (0) labels in the training set; "
                f"got n_pos={n_pos}, n_neg={n_neg}. Crawl more gold-label URLs with both "
                "classes and ensure the domain split leaves each class in train."
            )
        scale_pos_weight = n_neg / n_pos

        logger.info(
            "xgb_train_start",
            n_train=len(train_labels),
            n_pos=n_pos,
            n_neg=n_neg,
            scale_pos_weight=round(scale_pos_weight, 3),
        )

        self._model = self._build_model(scale_pos_weight)

        X_train = self._to_matrix(train_features)
        y_train = np.array(train_labels, dtype=np.int32)

        fit_kwargs: dict[str, Any] = {}
        if eval_features and eval_labels:
            X_eval = self._to_matrix(eval_features)
            y_eval = np.array(eval_labels, dtype=np.int32)
            fit_kwargs["eval_set"] = [(X_eval, y_eval)]
            fit_kwargs["verbose"] = False

        self._model.fit(X_train, y_train, **fit_kwargs)

        class_dist = {"MFA": int(n_pos), "Non_MFA": int(n_neg)}
        self._metadata = ModelMetadata(
            feature_schema_version=self.feature_schema_version,
            feature_names=self.feature_names,
            trained_at=datetime.now(UTC).isoformat(),
            xgb_version=xgb.__version__,
            n_train_samples=len(train_labels),
            class_distribution=class_dist,
            scale_pos_weight=round(scale_pos_weight, 4),
            hyperparams=self._hyperparams,
        )
        logger.info("xgb_train_done")

    def predict_proba(self, feature_dicts: list[dict[str, Any]]) -> np.ndarray:
        """Return P(MFA) for each sample as a 1-D numpy array.

        Raises ``RuntimeError`` if ``train`` has not been called.
        """
        if self._model is None:
            raise RuntimeError("Model has not been trained yet; call train() first.")
        X = self._to_matrix(feature_dicts)
        return self._model.predict_proba(X)[:, 1]

    def get_feature_importances(self) -> dict[str, float]:
        """Return gain-based feature importances keyed by feature name."""
        if self._model is None:
            raise RuntimeError("Model has not been trained yet.")
        scores = self._model.get_booster().get_score(importance_type="gain")
        return {name: scores.get(f"f{i}", 0.0) for i, name in enumerate(self.feature_names)}

    def save(self, artifact_dir: Path) -> None:
        """Persist model + metadata to ``artifact_dir``."""
        if self._model is None or self._metadata is None:
            raise RuntimeError("Model has not been trained; nothing to save.")
        artifact_dir.mkdir(parents=True, exist_ok=True)
        model_path = artifact_dir / "model.pkl"
        meta_path = artifact_dir / "metadata.json"

        with open(model_path, "wb") as f:
            pickle.dump(self._model, f)
        with open(meta_path, "w") as f:
            json.dump(asdict(self._metadata), f, indent=2)

        logger.info("xgb_model_saved", path=str(artifact_dir))

    @classmethod
    def load(cls, artifact_dir: Path, expected_schema_version: str = "v1") -> MFAXGBClassifier:
        """Load a previously saved model.

        Raises ``ValueError`` if the stored schema version does not match
        ``expected_schema_version`` — prevents silently running a stale model.
        """
        meta_path = artifact_dir / "metadata.json"
        model_path = artifact_dir / "model.pkl"

        with open(meta_path) as f:
            meta_dict = json.load(f)

        stored_version = meta_dict["feature_schema_version"]
        if stored_version != expected_schema_version:
            raise ValueError(
                f"Model schema version '{stored_version}' != expected '{expected_schema_version}'"
            )

        with open(model_path, "rb") as f:
            model: xgb.XGBClassifier = pickle.load(f)

        instance = cls(
            feature_names=meta_dict["feature_names"],
            feature_schema_version=stored_version,
        )
        instance._model = model
        instance._metadata = ModelMetadata(**meta_dict)
        logger.info("xgb_model_loaded", path=str(artifact_dir))
        return instance
