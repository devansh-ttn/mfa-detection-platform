"""Tests for model_eval empty-database handling."""

from pathlib import Path

import pytest

from mfa_ml.eval.model_eval import evaluate_model


def test_evaluate_model_skips_when_no_snapshots(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    gold = tmp_path / "gold.jsonl"
    gold.write_text(
        '{"url": "https://example.com", "domain": "example.com", "gold_label": "MFA_High"}\n',
        encoding="utf-8",
    )
    artifact_dir = tmp_path / "artifacts"
    artifact_dir.mkdir()

    class _EmptyExtractor:
        def __init__(self, *_args, **_kwargs):
            pass

        def load(self):
            return []

    monkeypatch.setattr("mfa_ml.eval.model_eval.FeatureExtractor", _EmptyExtractor)

    metrics = evaluate_model(
        db_url="postgresql://mfa:mfa@localhost:5432/mfa",
        gold_labels_path=gold,
        artifact_dir=artifact_dir,
        eval_all=True,
    )
    assert metrics["n_evaluated"] == 0
    assert metrics["skipped_reason"] == "no_crawled_snapshots"
    assert (artifact_dir / "metrics.json").is_file()
