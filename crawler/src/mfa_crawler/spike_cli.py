"""CLI for the 100-domain crawler spike (POC-2.5)."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

import structlog
from mfa_common.logging import configure_logging

from mfa_crawler.spike import write_spike_report, run_spike

logger = structlog.get_logger(__name__)

DEFAULT_OUTPUT_DIR = Path("crawler/artifacts/crawl_spike")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run crawler spike on domains from data/seed/domains_summary.csv",
    )
    parser.add_argument(
        "--domains",
        type=int,
        default=100,
        help="Number of domains to crawl (default: 100)",
    )
    parser.add_argument(
        "--delay-sec",
        type=float,
        default=1.0,
        help="Delay between crawls to reduce load on target sites (default: 1.0)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Directory for report.json and report.md (default: {DEFAULT_OUTPUT_DIR})",
    )
    return parser


async def _main_async(args: argparse.Namespace) -> int:
    if args.domains < 1:
        print("error: --domains must be >= 1", file=sys.stderr)
        return 2
    if args.delay_sec < 0:
        print("error: --delay-sec must be >= 0", file=sys.stderr)
        return 2

    report = await run_spike(domain_limit=args.domains, delay_sec=args.delay_sec)
    json_path, md_path = write_spike_report(report, args.output_dir)

    logger.info(
        "crawl_spike_report_written",
        json_path=str(json_path),
        markdown_path=str(md_path),
        success_rate=report["success_rate"],
    )
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print(
        f"Success rate: {report['success_rate']:.1%} "
        f"({report['succeeded']}/{report['attempted']}); "
        f"median crawl: {report['crawl_duration_sec']['median']}s"
    )
    return 0 if report["failed"] == 0 else 1


def main() -> None:
    configure_logging()
    args = _build_parser().parse_args()
    try:
        exit_code = asyncio.run(_main_async(args))
    except Exception:
        logger.exception("crawl_spike_failed")
        sys.exit(1)
    else:
        sys.exit(exit_code)


if __name__ == "__main__":
    main()
