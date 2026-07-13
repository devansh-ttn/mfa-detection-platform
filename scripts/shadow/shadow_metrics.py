#!/usr/bin/env python3
"""Shadow mode weekly metrics rollup (MVP-5.1).

Reads daily blocklist exports and reviewer queue stats for go/no-go gates.

Usage:
    uv run python scripts/shadow/shadow_metrics.py
    uv run python scripts/shadow/shadow_metrics.py --week 2 --export-dir ./data/shadow
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def _load_exports(export_dir: Path) -> list[dict]:
    files = sorted(export_dir.glob("blocklist_mfa_high_*.json"))
    exports: list[dict] = []
    for path in files:
        try:
            exports.append(json.loads(path.read_text()))
        except (json.JSONDecodeError, OSError):
            continue
    return exports


def main() -> None:
    parser = argparse.ArgumentParser(description="Shadow mode metrics rollup")
    parser.add_argument("--export-dir", default="./data/shadow", type=Path)
    parser.add_argument("--week", type=int, default=None, help="Report week number (1-4)")
    args = parser.parse_args()

    exports = _load_exports(args.export_dir)
    if not exports:
        print("No shadow exports found. Run scripts/shadow/daily_blocklist_export.sh daily.")
        return

    totals = [e.get("total", 0) for e in exports]
    latest = exports[-1]
    print("Shadow mode metrics")
    print(f"  Export files: {len(exports)}")
    print(f"  Latest MFA_High total: {latest.get('total', 0)}")
    print(f"  Avg daily total: {sum(totals) / len(totals):.1f}")
    print(f"  Shadow mode flag on API: {latest.get('shadow_mode', 'unknown')}")

    if args.week:
        print(f"\nWeek {args.week} checklist (see docs/runbooks/shadow-mode.md):")
        gates = [
            ("Shadow precision (reviewer sample)", "≥85%"),
            ("False positive rate (top publishers)", "<5%"),
            ("Reviewer SLA (uncertain high-spend)", "24h"),
            ("MVP-5.4 security review", "complete"),
        ]
        for name, target in gates:
            print(f"  [ ] {name}: {target}")


if __name__ == "__main__":
    main()
