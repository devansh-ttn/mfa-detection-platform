#!/usr/bin/env python3
"""Validate gold_labels seed files against schema and business rules."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SEED_DIR = REPO_ROOT / "data" / "seed"


def main() -> int:
    csv_path = SEED_DIR / "gold_labels.csv"
    jsonl_path = SEED_DIR / "gold_labels.jsonl"
    manifest_path = SEED_DIR / "manifest.json"

    if not csv_path.exists():
        print(f"Missing {csv_path}; run build_gold_labels.py first")
        return 1

    with csv_path.open(encoding="utf-8") as f:
        csv_rows = list(csv.DictReader(f))

    with jsonl_path.open(encoding="utf-8") as f:
        jsonl_rows = [json.loads(line) for line in f if line.strip()]

    if len(csv_rows) != len(jsonl_rows):
        print(f"Row count mismatch: CSV={len(csv_rows)} JSONL={len(jsonl_rows)}")
        return 1

    with manifest_path.open(encoding="utf-8") as f:
        manifest = json.load(f)

    if manifest["record_count"] != len(csv_rows):
        print(f"Manifest count mismatch: {manifest['record_count']} vs {len(csv_rows)}")
        return 1

    errors: list[str] = []
    if len(csv_rows) < 100:
        errors.append(f"Only {len(csv_rows)} records (minimum 100)")

    labels: dict[str, int] = {}
    for row in csv_rows:
        labels[row["gold_label"]] = labels.get(row["gold_label"], 0) + 1

    if labels.get("MFA_High", 0) < 50:
        errors.append("MFA_High count below 50")
    if labels.get("Non_MFA", 0) < 50:
        errors.append("Non_MFA count below 50")

    if errors:
        for e in errors:
            print(f"ERROR: {e}")
        return 1

    print(f"OK: {len(csv_rows)} records validated")
    print(f"  Labels: {labels}")
    print(f"  Domains: {manifest['unique_domains']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
