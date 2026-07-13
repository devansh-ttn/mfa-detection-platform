#!/usr/bin/env python3
"""Ingest DSP inventory CSV into the MFA ingestion API (MVP-5.2).

Expected CSV columns: url (required), optional priority, source_batch_id.

Usage:
    uv run python scripts/ingest/dsp_inventory.py --file inventory.csv
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import httpx


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest DSP inventory CSV")
    parser.add_argument("--file", type=Path, required=True)
    parser.add_argument("--api-url", default="http://localhost:8000")
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--source-batch-id", default="dsp-import")
    parser.add_argument("--priority", type=int, default=5)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    urls: list[str] = []
    with args.file.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            url = row.get("url") or row.get("URL") or row.get("page_url")
            if url:
                urls.append(url.strip())

    if not urls:
        raise SystemExit("No URLs found in CSV")

    print(f"Found {len(urls)} URLs")
    if args.dry_run:
        print("Dry run — no API calls")
        return

    accepted = duplicate = 0
    with httpx.Client(base_url=args.api_url, timeout=60.0) as client:
        for i in range(0, len(urls), args.batch_size):
            batch = urls[i : i + args.batch_size]
            resp = client.post(
                "/api/v1/urls",
                json={
                    "urls": batch,
                    "source_batch_id": args.source_batch_id,
                    "priority": args.priority,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            accepted += data.get("accepted", 0)
            duplicate += data.get("duplicate", 0)

    print(json.dumps({"accepted": accepted, "duplicate": duplicate, "total": len(urls)}))


if __name__ == "__main__":
    main()
