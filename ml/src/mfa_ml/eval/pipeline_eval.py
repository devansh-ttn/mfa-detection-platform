"""Live pipeline evaluation — compare stored classifications to gold labels."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog

from mfa_ml.data.loader import _BINARY_LABEL, _normalize_url
from mfa_ml.eval.metrics import build_metrics, predicted_tier_is_mfa

logger = structlog.get_logger(__name__)

POC_PRECISION_TARGET = 0.85
POC_RECALL_TARGET = 0.70


def _load_gold_labels(path: Path) -> dict[str, tuple[str, str, str]]:
    result: dict[str, tuple[str, str, str]] = {}
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            _, url_hash = _normalize_url(record["url"])
            result[url_hash] = (record["url"], record["domain"], record["gold_label"])
    return result


def _load_latest_classifications(db_url: str) -> dict[str, dict[str, Any]]:
    import psycopg

    query = """
        SELECT u.url_hash,
               u.url,
               u.domain,
               c.tier,
               c.mfa_score,
               c.confidence,
               c.evidence_hash
        FROM classifications c
        JOIN urls u ON c.url_id = u.id
        WHERE c.created_at = (
            SELECT MAX(c2.created_at)
            FROM classifications c2
            WHERE c2.url_id = c.url_id
        )
    """
    result: dict[str, dict[str, Any]] = {}
    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            for row in cur.fetchall():
                url_hash, url, domain, tier, mfa_score, confidence, evidence_hash = row
                result[url_hash] = {
                    "url": url,
                    "domain": domain,
                    "tier": tier,
                    "mfa_score": float(mfa_score),
                    "confidence": confidence,
                    "evidence_hash": evidence_hash or "",
                }
    return result


def evaluate_live_pipeline(
    db_url: str,
    gold_labels_path: Path,
    *,
    precision_target: float = POC_PRECISION_TARGET,
    recall_target: float = POC_RECALL_TARGET,
) -> dict[str, Any]:
    """Evaluate latest DB classifications against gold labels."""
    gold = _load_gold_labels(gold_labels_path)
    predictions = _load_latest_classifications(db_url)

    y_true: list[int] = []
    y_pred: list[int] = []
    tiers: list[str] = []
    skipped_uncertain = 0
    skipped_no_classification = 0

    for url_hash, (_url, _domain, gold_label) in gold.items():
        binary = _BINARY_LABEL.get(gold_label)
        if binary is None:
            skipped_uncertain += 1
            continue
        pred = predictions.get(url_hash)
        if pred is None:
            skipped_no_classification += 1
            continue
        y_true.append(binary)
        tier = pred["tier"]
        tiers.append(tier)
        y_pred.append(1 if predicted_tier_is_mfa(tier) else 0)

    metrics = build_metrics(
        y_true=y_true,
        y_pred=y_pred,
        predicted_tiers=tiers,
        n_total=len(gold),
        eval_mode="live_pipeline",
        precision_target=precision_target,
        recall_target=recall_target,
        extra={
            "evaluated_at": datetime.now(UTC).isoformat(),
            "gold_label_total": len(gold),
            "skipped_uncertain_gold": skipped_uncertain,
            "skipped_no_classification": skipped_no_classification,
        },
    )
    logger.info(
        "live_pipeline_eval",
        n_evaluated=metrics["n_evaluated"],
        precision=metrics["precision"],
        recall=metrics["recall"],
    )
    return metrics
