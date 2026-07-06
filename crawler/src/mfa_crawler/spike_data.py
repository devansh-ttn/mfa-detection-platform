"""Load seed domains and URLs for crawler spike evaluation."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SEED_DIR = REPO_ROOT / "data" / "seed"
DOMAINS_SUMMARY_PATH = SEED_DIR / "domains_summary.csv"
GOLD_LABELS_PATH = SEED_DIR / "gold_labels.jsonl"

PAGE_TYPE_PRIORITY = {
    "article": 0,
    "category": 1,
    "homepage": 2,
}


@dataclass(frozen=True)
class SpikeTarget:
    domain: str
    candidate_urls: tuple[str, ...]
    primary_gold_label: str
    content_category: str
    label_source: str

    @property
    def url(self) -> str:
        """Primary URL (first candidate)."""
        return self.candidate_urls[0]


def load_domain_rows(*, limit: int = 100) -> list[dict[str, str]]:
    if not DOMAINS_SUMMARY_PATH.exists():
        raise FileNotFoundError(f"domains summary not found: {DOMAINS_SUMMARY_PATH}")

    rows: list[dict[str, str]] = []
    with DOMAINS_SUMMARY_PATH.open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            rows.append(row)
            if len(rows) >= limit:
                break
    if not rows:
        raise ValueError(f"No domains found in {DOMAINS_SUMMARY_PATH}")
    return rows


def _load_gold_label_records() -> list[dict]:
    if not GOLD_LABELS_PATH.exists():
        raise FileNotFoundError(f"gold labels not found: {GOLD_LABELS_PATH}")

    records: list[dict] = []
    with GOLD_LABELS_PATH.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def list_urls_for_domain(records: list[dict], domain: str) -> list[str]:
    """Return candidate URLs for a domain, best page types first."""
    candidates = [record for record in records if record.get("domain") == domain]
    if not candidates:
        return []
    candidates.sort(
        key=lambda record: (
            PAGE_TYPE_PRIORITY.get(record.get("page_type", ""), 99),
            record.get("url", ""),
        )
    )
    return [record["url"] for record in candidates]


def load_spike_targets(*, domain_limit: int = 100) -> list[SpikeTarget]:
    """Select one representative URL per domain from the seed corpus."""
    domain_rows = load_domain_rows(limit=domain_limit)
    records = _load_gold_label_records()

    targets: list[SpikeTarget] = []
    missing: list[str] = []
    for row in domain_rows:
        domain = row["domain"]
        candidate_urls = list_urls_for_domain(records, domain)
        if not candidate_urls:
            missing.append(domain)
            continue
        targets.append(
            SpikeTarget(
                domain=domain,
                candidate_urls=tuple(candidate_urls),
                primary_gold_label=row["primary_gold_label"],
                content_category=row["content_category"],
                label_source=row["label_source"],
            )
        )

    if missing:
        raise ValueError(f"No gold-label URL found for domains: {', '.join(missing)}")
    return targets
