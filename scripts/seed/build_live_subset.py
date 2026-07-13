#!/usr/bin/env python3
"""Build a crawl-friendly gold-label subset for MVP retrain and batch eval.

Excludes URLs listed in unreachable_urls.csv (from audit_unreachable_urls.py)
and optional synthetic paths on major publisher domains that fail with 404.

Usage:
    uv run python scripts/seed/build_live_subset.py
    uv run python scripts/seed/build_live_subset.py --use-subset-100
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_GOLD = REPO_ROOT / "data/seed/gold_labels.jsonl"
DEFAULT_UNREACHABLE = REPO_ROOT / "data/seed/unreachable_urls.csv"
DEFAULT_SUBSET_100 = REPO_ROOT / "data/seed/subset_100_domains.json"
DEFAULT_OUTPUT = REPO_ROOT / "data/seed/gold_labels_live.jsonl"

# Major publishers where category/article paths in seed data are synthetic 404s.
SYNTHETIC_PUBLISHER_DOMAINS = frozenset(
    {
        "wsj.com",
        "bloomberg.com",
        "washingtonpost.com",
        "economist.com",
        "telegraph.co.uk",
        "dailymail.co.uk",
        "mayoclinic.org",
        "tripadvisor.com",
        "marketwatch.com",
        "fastcompany.com",
        "inc.com",
        "edmunds.com",
        "sciencepicker.com",
    }
)


def load_unreachable(path: Path) -> set[str]:
    if not path.exists():
        return set()
    urls: set[str] = set()
    with path.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            if row.get("url"):
                urls.add(row["url"])
    return urls


def is_synthetic_publisher_path(url: str) -> bool:
    parsed = urlparse(url)
    domain = parsed.netloc.removeprefix("www.")
    if domain not in SYNTHETIC_PUBLISHER_DOMAINS:
        return False
    path = parsed.path.rstrip("/")
    return path not in {"", "/"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Build live gold-label subset")
    parser.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    parser.add_argument("--unreachable", type=Path, default=DEFAULT_UNREACHABLE)
    parser.add_argument("--subset-100", type=Path, default=DEFAULT_SUBSET_100)
    parser.add_argument("--use-subset-100", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    unreachable = load_unreachable(args.unreachable)
    subset_urls: set[str] | None = None
    if args.use_subset_100 and args.subset_100.exists():
        subset_urls = set(json.loads(args.subset_100.read_text(encoding="utf-8")))

    kept: list[dict] = []
    excluded = {"unreachable": 0, "synthetic_publisher": 0, "not_in_subset": 0}

    with args.gold.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            url = rec["url"]
            if url in unreachable:
                excluded["unreachable"] += 1
                continue
            if is_synthetic_publisher_path(url):
                excluded["synthetic_publisher"] += 1
                continue
            if subset_urls is not None and url not in subset_urls:
                excluded["not_in_subset"] += 1
                continue
            kept.append(rec)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as fh:
        for rec in kept:
            fh.write(json.dumps(rec) + "\n")

    print(f"Wrote {len(kept)} labels to {args.output}")
    for reason, count in excluded.items():
        if count:
            print(f"  excluded ({reason}): {count}")


if __name__ == "__main__":
    main()
