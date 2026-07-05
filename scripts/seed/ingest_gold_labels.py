#!/usr/bin/env python3
"""Batch-ingest gold-label seed URLs via POST /api/v1/urls.

Reads `data/seed/gold_labels.jsonl`, sends URLs in batches (API max 500/request),
and reports accepted / duplicate / invalid counts.

Examples:
  # Smoke test (5 URLs) — API must be running
  python scripts/seed/ingest_gold_labels.py --limit 5

  # Full dataset (615 URLs, batched)
  python scripts/seed/ingest_gold_labels.py

  # Crawler spike — first 100 domains from domains_summary.csv
  python scripts/seed/ingest_gold_labels.py --subset-domains 100

  # Custom API base URL
  python scripts/seed/ingest_gold_labels.py --api-url http://localhost:8000
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SEED_DIR = REPO_ROOT / "data" / "seed"
DEFAULT_BATCH_SIZE = 500


def load_manifest() -> dict:
    with (SEED_DIR / "manifest.json").open(encoding="utf-8") as f:
        return json.load(f)


def load_urls_from_jsonl(*, limit: int | None) -> list[str]:
    jsonl_path = SEED_DIR / "gold_labels.jsonl"
    urls: list[str] = []
    with jsonl_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            urls.append(record["url"])
            if limit is not None and len(urls) >= limit:
                break
    return urls


def load_urls_from_file(path: Path) -> list[str]:
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list) or not all(isinstance(u, str) for u in data):
        raise ValueError(f"{path} must be a JSON array of URL strings")
    return data


def load_domain_subset(*, domain_count: int) -> set[str]:
    summary_path = SEED_DIR / "domains_summary.csv"
    if not summary_path.exists():
        raise FileNotFoundError(
            f"{summary_path} not found; run: python scripts/seed/export_domains_summary.py"
        )
    domains: list[str] = []
    with summary_path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            domains.append(row["domain"])
            if len(domains) >= domain_count:
                break
    if not domains:
        raise ValueError(f"No domains found in {summary_path}")
    return set(domains)


def load_urls_for_domains(domain_set: set[str]) -> list[str]:
    jsonl_path = SEED_DIR / "gold_labels.jsonl"
    urls: list[str] = []
    with jsonl_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            if record["domain"] in domain_set:
                urls.append(record["url"])
    return urls


def write_url_list(path: Path, urls: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(urls, indent=2), encoding="utf-8")


def post_batch(
    api_url: str,
    urls: list[str],
    *,
    source_batch_id: str,
    priority: int,
    dry_run: bool,
) -> dict:
    payload = {
        "urls": urls,
        "source_batch_id": source_batch_id,
        "priority": priority,
    }
    if dry_run:
        return {"accepted": len(urls), "duplicate": 0, "invalid": [], "jobs": []}

    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{api_url.rstrip('/')}/api/v1/urls",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode("utf-8"))


def chunked(items: list[str], size: int) -> list[list[str]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest gold-label seed URLs via API")
    parser.add_argument(
        "--api-url",
        default="http://localhost:8000",
        help="Backend API base URL (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--source-batch-id",
        default=None,
        help="source_batch_id for crawl jobs (default: manifest version)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Ingest only the first N URLs from the source (smoke test)",
    )
    parser.add_argument(
        "--url-file",
        type=Path,
        default=None,
        help="JSON file with a URL array (overrides gold_labels.jsonl)",
    )
    parser.add_argument(
        "--subset-domains",
        type=int,
        default=None,
        metavar="N",
        help="Ingest URLs for the first N domains in domains_summary.csv",
    )
    parser.add_argument(
        "--write-subset",
        type=Path,
        default=None,
        metavar="PATH",
        help="Write selected URLs to a JSON file (use with --subset-domains)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=f"URLs per API request (max 500, default: {DEFAULT_BATCH_SIZE})",
    )
    parser.add_argument("--priority", type=int, default=1, help="Crawl job priority 0–100")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print batches without calling the API",
    )
    args = parser.parse_args()

    if args.batch_size < 1 or args.batch_size > 500:
        print("ERROR: --batch-size must be between 1 and 500")
        return 1
    if args.subset_domains is not None and args.subset_domains < 1:
        print("ERROR: --subset-domains must be >= 1")
        return 1
    if args.url_file is not None and args.subset_domains is not None:
        print("ERROR: use either --url-file or --subset-domains, not both")
        return 1

    manifest = load_manifest()
    source_batch_id = args.source_batch_id or manifest["version"]

    try:
        if args.url_file is not None:
            urls = load_urls_from_file(args.url_file)
        elif args.subset_domains is not None:
            domain_set = load_domain_subset(domain_count=args.subset_domains)
            urls = load_urls_for_domains(domain_set)
            print(
                f"Subset: {args.subset_domains} domain(s) -> {len(urls)} URL(s) "
                f"from {SEED_DIR / 'gold_labels.jsonl'}"
            )
        else:
            urls = load_urls_from_jsonl(limit=args.limit)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}")
        if args.url_file is not None:
            print(
                "Generate a subset file with:\n"
                "  python scripts/seed/ingest_gold_labels.py --subset-domains 100 "
                "--write-subset data/seed/subset_100_domains.json --dry-run"
            )
        return 1
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"ERROR: {exc}")
        return 1

    if args.limit is not None:
        urls = urls[: args.limit]

    if args.write_subset is not None:
        write_url_list(args.write_subset, urls)
        print(f"Wrote {len(urls)} URL(s) to {args.write_subset}")
        if args.dry_run:
            return 0

    if not urls:
        source = args.url_file or (SEED_DIR / "gold_labels.jsonl")
        print(f"No URLs found in {source}")
        return 1

    totals = {"accepted": 0, "duplicate": 0, "invalid": 0, "batches": 0}

    print(f"Ingesting {len(urls)} URL(s) with source_batch_id={source_batch_id!r}")
    if args.dry_run:
        print("DRY RUN — no API calls")

    for batch_num, batch in enumerate(chunked(urls, args.batch_size), start=1):
        try:
            result = post_batch(
                args.api_url,
                batch,
                source_batch_id=source_batch_id,
                priority=args.priority,
                dry_run=args.dry_run,
            )
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            print(f"ERROR batch {batch_num}: HTTP {exc.code} — {detail}")
            return 1
        except urllib.error.URLError as exc:
            print(f"ERROR batch {batch_num}: cannot reach API at {args.api_url} — {exc.reason}")
            print("Start the stack first: docker compose up -d")
            return 1

        totals["batches"] += 1
        totals["accepted"] += result.get("accepted", 0)
        totals["duplicate"] += result.get("duplicate", 0)
        totals["invalid"] += len(result.get("invalid", []))

        print(
            f"  batch {batch_num}: sent={len(batch)} "
            f"accepted={result.get('accepted', 0)} "
            f"duplicate={result.get('duplicate', 0)} "
            f"invalid={len(result.get('invalid', []))}"
        )
        for invalid in result.get("invalid", []):
            print(f"    invalid: {invalid}")

    print(
        f"Done: {totals['batches']} batch(es), "
        f"accepted={totals['accepted']}, duplicate={totals['duplicate']}, "
        f"invalid={totals['invalid']}"
    )
    if totals["duplicate"] and totals["accepted"] == 0:
        print("Note: all URLs were already ingested (idempotent re-run).")
    return 0 if totals["invalid"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
