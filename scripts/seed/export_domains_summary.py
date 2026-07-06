#!/usr/bin/env python3
"""Export unique domains with primary gold label for crawler subset selection."""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SEED_DIR = REPO_ROOT / "data" / "seed"

# Priority order when a domain has mixed labels (should not happen in current seed)
LABEL_PRIORITY = ["MFA_High", "MFA_Medium", "MFA_Low", "Uncertain", "Non_MFA"]


def main() -> None:
    csv_path = SEED_DIR / "gold_labels.csv"
    out_path = SEED_DIR / "domains_summary.csv"

    by_domain: dict[str, dict] = defaultdict(
        lambda: {"url_count": 0, "labels": set(), "category": "", "source": ""}
    )

    with csv_path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            d = by_domain[row["domain"]]
            d["url_count"] += 1
            d["labels"].add(row["gold_label"])
            d["category"] = row["content_category"]
            d["source"] = row["label_source"]

    rows: list[dict] = []
    for domain, info in sorted(by_domain.items()):
        primary = min(info["labels"], key=lambda x: LABEL_PRIORITY.index(x))
        rows.append(
            {
                "domain": domain,
                "primary_gold_label": primary,
                "url_count": info["url_count"],
                "content_category": info["category"],
                "label_source": info["source"],
            }
        )

    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["domain", "primary_gold_label", "url_count", "content_category", "label_source"],
        )
        writer.writeheader()
        writer.writerows(rows)

    mfa_domains = sum(1 for r in rows if r["primary_gold_label"].startswith("MFA"))
    non_mfa = sum(1 for r in rows if r["primary_gold_label"] == "Non_MFA")
    print(f"Wrote {len(rows)} domains to {out_path}")
    print(f"  MFA domains: {mfa_domains}, Non_MFA domains: {non_mfa}")


if __name__ == "__main__":
    main()
