#!/usr/bin/env python3
"""Export latest classifications for Ad Ops HITL review (POC-5.5).

Queries Postgres for the latest classification per URL, filtered by tier,
and writes a CSV suitable for spreadsheet review.

Examples:
  # Default: MFA_Medium and Uncertain tiers
  uv run --package mfa-backend python scripts/export/reviewer_csv.py

  # Custom output path and tiers
  uv run --package mfa-backend python scripts/export/reviewer_csv.py \\
      --output reviewer_queue.csv \\
      --tier MFA_Medium,Uncertain

  # Filter by domain
  uv run --package mfa-backend python scripts/export/reviewer_csv.py \\
      --domain example.com \\
      --tier MFA_High
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import sys
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from mfa.db.models import Classification, Url
from mfa.scoring.classification_list import (
    classification_index_stmt,
    latest_classification_ids_stmt,
    parse_confidence_filter,
    parse_tier_filter,
)

DEFAULT_TIERS = ["MFA_Medium", "Uncertain"]
CSV_COLUMNS = (
    "url",
    "domain",
    "tier",
    "mfa_score",
    "confidence",
    "top_signals",
    "explanation",
    "evidence_hash",
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export reviewer HITL queue to CSV")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("reviewer_queue.csv"),
        help="Output CSV path (default: reviewer_queue.csv)",
    )
    parser.add_argument(
        "--tier",
        default=",".join(DEFAULT_TIERS),
        help="Comma-separated tier filter (default: MFA_Medium,Uncertain)",
    )
    parser.add_argument(
        "--confidence",
        default=None,
        help="Optional comma-separated confidence filter (high,medium,low)",
    )
    parser.add_argument(
        "--domain",
        default=None,
        help="Optional domain filter",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=5000,
        help="Maximum rows to export (default: 5000)",
    )
    parser.add_argument(
        "--database-url",
        default=os.getenv(
            "DATABASE_URL",
            "postgresql+asyncpg://mfa:mfa@localhost:5432/mfa",
        ),
        help="Async SQLAlchemy database URL",
    )
    return parser.parse_args()


async def _fetch_rows(
    session: AsyncSession,
    *,
    tier: list[str] | None,
    confidence: list[str] | None,
    domain: str | None,
    limit: int,
) -> list[tuple[Classification, Url]]:
    id_stmt = latest_classification_ids_stmt(tier=tier, domain=domain, confidence=confidence)
    page_ids = id_stmt.limit(limit)
    result = await session.execute(classification_index_stmt(page_ids))
    return list(result.all())


def _write_csv(rows: list[tuple[Classification, Url]], output: Path) -> int:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for classification, url_row in rows:
            writer.writerow(
                {
                    "url": url_row.url,
                    "domain": url_row.domain,
                    "tier": classification.tier,
                    "mfa_score": classification.mfa_score,
                    "confidence": classification.confidence,
                    "top_signals": json.dumps(classification.top_signals, separators=(",", ":")),
                    "explanation": classification.explanation,
                    "evidence_hash": classification.evidence_hash,
                }
            )
    return len(rows)


async def _run(args: argparse.Namespace) -> int:
    try:
        tier = parse_tier_filter([args.tier])
        confidence = parse_confidence_filter([args.confidence] if args.confidence else None)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    engine = create_async_engine(args.database_url, pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        rows = await _fetch_rows(
            session,
            tier=tier,
            confidence=confidence,
            domain=args.domain,
            limit=args.limit,
        )

    count = _write_csv(rows, args.output)
    print(f"Wrote {count} row(s) to {args.output}")
    await engine.dispose()
    return 0


def main() -> None:
    args = _parse_args()
    raise SystemExit(asyncio.run(_run(args)))


if __name__ == "__main__":
    main()
