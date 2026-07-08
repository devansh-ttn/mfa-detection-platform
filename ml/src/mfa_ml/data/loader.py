"""Training data loader — joins gold labels with crawled signal_snapshots.

Workflow:
1. Load gold_labels.jsonl → {url_hash: (domain, binary_label)} mapping.
2. Query Postgres for the latest signal_snapshot per url (by url_hash).
3. Join and return ``LabeledSample`` list with features + label + domain.

Label mapping (binary for POC):
    MFA_High   → 1
    MFA_Medium → 1   (TODO: present in MVP gold labels)
    MFA_Low    → 0
    Non_MFA    → 0
    Uncertain  → skipped (excluded from training)

Features with null values are passed through as-is; the classifier
handles imputation via the ``SENTINEL_NULL`` convention.

Docs: docs/SIGNALS.md · docs/plans/2026-07-05-phased-build-plan.md (POC-3.2)
"""

from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, urlunparse

import structlog

logger = structlog.get_logger(__name__)

CRAWL_FEATURE_NAMES: tuple[str, ...] = (
    "ad_to_content_ratio",
    "ads_above_fold",
    "ad_slots_count",
    "sticky_ad_count",
    "content_word_count",
    "refresh_events_60s",
    "avg_refresh_interval_sec",
    "content_uniqueness_score",
    "author_page_exists",
    "slideshow_pagination_depth",
    "video_autoplay_count",
    "page_load_ad_latency_ms",
    "iframe_ad_count",
    "native_ad_count",
    "outbound_link_count",
    "image_to_text_ratio",
)

_BINARY_LABEL: dict[str, int | None] = {
    "MFA_High": 1,
    "MFA_Medium": 1,
    "MFA_Low": 0,
    "Non_MFA": 0,
    "Uncertain": None,
}


@dataclass
class LabeledSample:
    """One training / evaluation record."""

    url: str
    domain: str
    url_hash: str
    label: int
    features: dict[str, Any]
    gold_label: str
    evidence_hash: str = ""


@dataclass
class DataSplit:
    """Domain-stratified 80/20 split."""

    train: list[LabeledSample] = field(default_factory=list)
    val: list[LabeledSample] = field(default_factory=list)

    @property
    def n_train(self) -> int:
        return len(self.train)

    @property
    def n_val(self) -> int:
        return len(self.val)

    def label_distribution(self, subset: str) -> dict[str, int]:
        samples = self.train if subset == "train" else self.val
        dist: dict[str, int] = {"MFA": 0, "Non_MFA": 0}
        for s in samples:
            key = "MFA" if s.label == 1 else "Non_MFA"
            dist[key] += 1
        return dist


def _normalize_url(raw: str) -> tuple[str, str]:
    """Return (normalized_url, url_hash) matching backend.ingestion.normalizer."""
    stripped = raw.strip()
    parsed = urlparse(stripped if "://" in stripped else f"https://{stripped}")
    scheme = (parsed.scheme or "https").lower()
    host = parsed.hostname.lower() if parsed.hostname else ""
    port = parsed.port
    default_port = 443 if scheme == "https" else 80
    netloc = host if port is None or port == default_port else f"{host}:{port}"
    path = parsed.path or "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    normalized = urlunparse((scheme, netloc, path, "", parsed.query, ""))
    url_hash = hashlib.sha256(normalized.encode()).hexdigest()
    return normalized, url_hash


def _extract_features(signals_jsonb: dict[str, Any]) -> dict[str, Any]:
    """Pull only CRAWL_FEATURE_NAMES from the flat JSONB dict."""
    return {name: signals_jsonb.get(name) for name in CRAWL_FEATURE_NAMES}


class FeatureExtractor:
    """Load and join gold labels with crawled signal_snapshots from Postgres.

    Args:
        database_url: Synchronous psycopg DSN,
            e.g. ``postgresql://user:pass@localhost:5432/mfadb``.
        gold_labels_path: Path to ``data/seed/gold_labels.jsonl``.
    """

    def __init__(self, database_url: str, gold_labels_path: Path) -> None:
        self._db_url = database_url
        self._labels_path = gold_labels_path

    def load(self) -> list[LabeledSample]:
        """Load and join gold labels with signal_snapshots.

        Returns:
            List of ``LabeledSample``.  URLs without a crawled snapshot are
            excluded.  ``Uncertain`` labels are excluded from training.
        """
        gold = self._load_gold_labels()
        snapshots = self._load_snapshots(set(gold.keys()))

        samples: list[LabeledSample] = []
        skipped_no_snapshot = 0
        skipped_uncertain = 0

        for url_hash, snap in snapshots.items():
            if url_hash not in gold:
                continue
            url, domain, gold_label = gold[url_hash]
            binary = _BINARY_LABEL.get(gold_label)
            if binary is None:
                skipped_uncertain += 1
                continue
            samples.append(
                LabeledSample(
                    url=url,
                    domain=domain,
                    url_hash=url_hash,
                    label=binary,
                    features=_extract_features(snap["signals"]),
                    gold_label=gold_label,
                    evidence_hash=snap.get("evidence_hash", ""),
                )
            )

        skipped_no_snapshot = len(gold) - len(snapshots)
        logger.info(
            "feature_extractor_load",
            n_samples=len(samples),
            skipped_no_snapshot=skipped_no_snapshot,
            skipped_uncertain=skipped_uncertain,
        )
        return samples

    def _load_gold_labels(self) -> dict[str, tuple[str, str, str]]:
        """Return {url_hash: (url, domain, gold_label)}."""
        result: dict[str, tuple[str, str, str]] = {}
        with open(self._labels_path) as f:
            for line in f:
                rec = json.loads(line)
                url = rec["url"]
                _, url_hash = _normalize_url(url)
                result[url_hash] = (url, rec["domain"], rec["gold_label"])
        logger.info("gold_labels_loaded", count=len(result))
        return result

    def _load_snapshots(
        self, url_hashes: set[str]
    ) -> dict[str, dict[str, Any]]:
        """Query Postgres for the latest signal_snapshot per URL hash.

        Returns {url_hash: {"signals": ..., "evidence_hash": ...}}.
        """
        import psycopg

        if not url_hashes:
            return {}

        hashes_list = list(url_hashes)
        query = """
            SELECT u.url_hash,
                   ss.signals,
                   ss.evidence_hash
            FROM signal_snapshots ss
            JOIN urls u ON ss.url_id = u.id
            WHERE u.url_hash = ANY(%s)
              AND ss.version = (
                  SELECT MAX(s2.version)
                  FROM signal_snapshots s2
                  WHERE s2.url_id = ss.url_id
              )
        """
        result: dict[str, dict[str, Any]] = {}
        with psycopg.connect(self._db_url) as conn:
            with conn.cursor() as cur:
                cur.execute(query, (hashes_list,))
                for row in cur.fetchall():
                    url_hash, signals, evidence_hash = row
                    result[url_hash] = {
                        "signals": signals if isinstance(signals, dict) else json.loads(signals),
                        "evidence_hash": evidence_hash or "",
                    }

        logger.info("snapshots_loaded", count=len(result))
        return result


def _val_domain_count(n_domains: int, val_fraction: float) -> int:
    """Hold out validation domains while keeping at least one domain in train."""
    if n_domains <= 1:
        return 0
    n_val = max(1, round(n_domains * val_fraction))
    return min(n_val, n_domains - 1)


def domain_stratified_split(
    samples: list[LabeledSample],
    val_fraction: float = 0.20,
    random_seed: int = 42,
) -> DataSplit:
    """Split samples by domain so no domain appears in both sets.

    Stratification ensures roughly the same MFA ratio in train and val.

    Args:
        samples: All labeled samples.
        val_fraction: Fraction of **domains** (not records) to hold out.
        random_seed: For reproducibility.

    Returns:
        ``DataSplit`` with train and val lists.
    """
    rng = random.Random(random_seed)

    domain_to_samples: dict[str, list[LabeledSample]] = {}
    for s in samples:
        domain_to_samples.setdefault(s.domain, []).append(s)

    mfa_domains = [d for d, samps in domain_to_samples.items() if any(s.label == 1 for s in samps)]
    non_mfa_domains = [
        d for d, samps in domain_to_samples.items() if all(s.label == 0 for s in samps)
    ]

    rng.shuffle(mfa_domains)
    rng.shuffle(non_mfa_domains)

    n_val_mfa = _val_domain_count(len(mfa_domains), val_fraction)
    n_val_non_mfa = _val_domain_count(len(non_mfa_domains), val_fraction)

    val_domains: set[str] = set(mfa_domains[:n_val_mfa]) | set(non_mfa_domains[:n_val_non_mfa])

    split = DataSplit()
    for s in samples:
        if s.domain in val_domains:
            split.val.append(s)
        else:
            split.train.append(s)

    logger.info(
        "domain_split",
        n_train=split.n_train,
        n_val=split.n_val,
        n_val_domains=len(val_domains),
        train_dist=split.label_distribution("train"),
        val_dist=split.label_distribution("val"),
    )
    return split
