#!/usr/bin/env python3
"""Validate gold_labels seed files against schema and business rules."""

from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SEED_DIR = REPO_ROOT / "data" / "seed"
SCHEMA_PATH = SEED_DIR / "schema" / "gold_label_record.schema.json"

RECORD_ID_RE = re.compile(r"^gl_[a-f0-9]{16}$")
GOLD_LABELS = {"MFA_High", "MFA_Medium", "MFA_Low", "Non_MFA", "Uncertain"}
LABEL_CONFIDENCE = {"high", "medium", "low"}
PAGE_TYPES = {"homepage", "article", "category", "slideshow", "section"}


def _validate_record(row: dict[str, str], line_no: int) -> list[str]:
    errors: list[str] = []
    required = (
        "record_id",
        "url",
        "domain",
        "gold_label",
        "label_source",
        "label_confidence",
        "page_type",
        "content_category",
        "notes",
        "source_batch_id",
        "created_at",
    )
    for field in required:
        if not row.get(field):
            errors.append(f"line {line_no}: missing required field {field!r}")

    record_id = row.get("record_id", "")
    if record_id and not RECORD_ID_RE.fullmatch(record_id):
        errors.append(f"line {line_no}: invalid record_id {record_id!r}")

    if row.get("gold_label") and row["gold_label"] not in GOLD_LABELS:
        errors.append(f"line {line_no}: invalid gold_label {row['gold_label']!r}")

    if row.get("label_confidence") and row["label_confidence"] not in LABEL_CONFIDENCE:
        errors.append(f"line {line_no}: invalid label_confidence {row['label_confidence']!r}")

    if row.get("page_type") and row["page_type"] not in PAGE_TYPES:
        errors.append(f"line {line_no}: invalid page_type {row['page_type']!r}")

    url = row.get("url", "")
    if url and not url.startswith(("http://", "https://")):
        errors.append(f"line {line_no}: url must be http(s): {url!r}")

    return errors


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
    for index, row in enumerate(csv_rows, start=2):
        labels[row["gold_label"]] = labels.get(row["gold_label"], 0) + 1
        errors.extend(_validate_record(row, index))

    for index, row in enumerate(jsonl_rows, start=1):
        if set(row.keys()) != set(csv_rows[0].keys()):
            errors.append(f"jsonl line {index}: field set mismatch vs CSV header")

    if labels.get("MFA_High", 0) < 50:
        errors.append("MFA_High count below 50")
    if labels.get("Non_MFA", 0) < 50:
        errors.append("Non_MFA count below 50")

    if SCHEMA_PATH.exists():
        with SCHEMA_PATH.open(encoding="utf-8") as f:
            schema = json.load(f)
        schema_required = set(schema.get("required", []))
        if schema_required - set(csv_rows[0].keys()):
            errors.append("CSV header missing schema required fields")

    if errors:
        for e in errors:
            print(f"ERROR: {e}")
        return 1

    print(f"OK: {len(csv_rows)} records validated against {SCHEMA_PATH.name}")
    print(f"  Labels: {labels}")
    print(f"  Domains: {manifest['unique_domains']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
