#!/usr/bin/env python3
"""Audit gold-label URLs against batch crawl failures for Ad Ops seed refresh.

Reads ``ml/artifacts/v1/batch_eval_report.json`` (or a custom report) and
emits a CSV of URLs that failed crawl with recommended actions.

Usage:
    uv run python scripts/seed/audit_unreachable_urls.py
    uv run python scripts/seed/audit_unreachable_urls.py --output data/seed/unreachable_urls.csv
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPORT = REPO_ROOT / "ml/artifacts/v1/batch_eval_report.json"
DEFAULT_GOLD = REPO_ROOT / "data/seed/gold_labels.jsonl"


def load_gold_labels(path: Path) -> dict[str, dict]:
    labels: dict[str, dict] = {}
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            labels[rec["url"]] = rec
    return labels


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit unreachable gold-label URLs")
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    parser.add_argument("--output", type=Path, default=REPO_ROOT / "data/seed/unreachable_urls.csv")
    args = parser.parse_args()

    if not args.report.exists():
        raise SystemExit(f"Batch report not found: {args.report}")

    report = json.loads(args.report.read_text(encoding="utf-8"))
    gold = load_gold_labels(args.gold)

    failures = report.get("crawl_failures", [])
    if not failures and "failed_jobs" in report:
        failures = report["failed_jobs"]

    # If report only has aggregate failure counts, advise re-run with DB export
    if not failures and "pipeline" in report:
        n_failed = report["pipeline"].get("crawl_jobs_by_status", {}).get("failed", 0)
        if n_failed:
            print(
                f"Report has {n_failed} failed crawls but no per-URL list. "
                "Query crawl_jobs WHERE status='failed' or re-run batch_pipeline_report with DB access."
            )
        return
    rows: list[dict[str, str]] = []
    for item in failures:
        url = item.get("url") or item.get("normalized_url", "")
        rec = item.get("record") or gold.get(url, {})
        error_type = item.get("crawl_error_type") or item.get("error_type", "unknown")
        action = "replace_with_live_inventory"
        if error_type == "not_found":
            action = "replace_synthetic_path_or_remove"
        elif error_type == "timeout":
            action = "retry_with_longer_timeout_or_remove"

        rows.append(
            {
                "url": url,
                "domain": rec.get("domain", ""),
                "gold_label": rec.get("gold_label", ""),
                "crawl_error_type": error_type,
                "recommended_action": action,
                "record_id": rec.get("record_id", ""),
            }
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["url", "domain", "gold_label", "crawl_error_type", "recommended_action", "record_id"]
    with args.output.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} unreachable URLs to {args.output}")
    by_type: dict[str, int] = {}
    for row in rows:
        by_type[row["crawl_error_type"]] = by_type.get(row["crawl_error_type"], 0) + 1
    for error_type, count in sorted(by_type.items(), key=lambda x: -x[1]):
        print(f"  {error_type}: {count}")


if __name__ == "__main__":
    main()
