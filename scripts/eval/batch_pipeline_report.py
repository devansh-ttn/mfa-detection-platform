#!/usr/bin/env python3
"""POC-5.3 batch pipeline report — ingest, monitor, and evaluate gold-label E2E.

Runs the full gold-label set through crawl → score, reports success rates,
and writes ``ml/artifacts/v1/batch_eval_report.json``.

Usage:
  # Full run: ingest 615 URLs, wait for workers, evaluate
  uv run --package mfa-ml python scripts/eval/batch_pipeline_report.py --ingest --wait

  # Report on current DB state only
  uv run --package mfa-ml python scripts/eval/batch_pipeline_report.py --report-only

  # Custom timeout (seconds) while waiting for workers
  uv run --package mfa-ml python scripts/eval/batch_pipeline_report.py --wait --timeout 7200
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import structlog
from mfa_common.logging import configure_logging

from mfa_ml.eval.model_eval import evaluate_model
from mfa_ml.eval.pipeline_eval import evaluate_live_pipeline

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_GOLD_LABELS = REPO_ROOT / "data" / "seed" / "gold_labels.jsonl"
DEFAULT_ARTIFACT_DIR = REPO_ROOT / "ml" / "artifacts" / "v1"
DEFAULT_REPORT_PATH = DEFAULT_ARTIFACT_DIR / "batch_eval_report.json"
CRAWL_SUCCESS_TARGET = 0.90


def _sync_db_url(async_url: str | None) -> str:
    url = async_url or os.getenv(
        "DATABASE_URL_SYNC",
        os.getenv("DATABASE_URL", "postgresql+asyncpg://mfa:mfa@localhost:5432/mfa"),
    )
    return url.replace("postgresql+asyncpg://", "postgresql://").replace(
        "postgresql+psycopg://", "postgresql://"
    )


def _count_gold_labels(path: Path) -> int:
    count = 0
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                count += 1
    return count


def _collect_pipeline_stats(db_url: str, gold_total: int) -> dict:
    import psycopg

    stats: dict = {"gold_label_total": gold_total}

    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM urls")
            stats["urls_in_db"] = int(cur.fetchone()[0])

            cur.execute(
                """
                SELECT status, count(*)
                FROM crawl_jobs
                GROUP BY status
                ORDER BY status
                """
            )
            crawl_by_status = {row[0]: int(row[1]) for row in cur.fetchall()}
            stats["crawl_jobs_by_status"] = crawl_by_status
            crawl_total = sum(crawl_by_status.values())
            crawl_completed = crawl_by_status.get("completed", 0)
            crawl_failed = crawl_by_status.get("failed", 0)
            crawl_terminal = crawl_completed + crawl_failed
            stats["crawl_success_rate"] = (
                round(crawl_completed / crawl_terminal, 4) if crawl_terminal else None
            )
            stats["crawl_success_target"] = CRAWL_SUCCESS_TARGET
            stats["crawl_success_met"] = (
                stats["crawl_success_rate"] is not None
                and stats["crawl_success_rate"] >= CRAWL_SUCCESS_TARGET
            )

            cur.execute(
                """
                SELECT crawl_error_type, count(*)
                FROM crawl_jobs
                WHERE status = 'failed'
                GROUP BY crawl_error_type
                ORDER BY count(*) DESC
                """
            )
            stats["crawl_failures_by_error_type"] = {
                (row[0] or "unknown"): int(row[1]) for row in cur.fetchall()
            }

            cur.execute(
                """
                SELECT u.domain, count(*)
                FROM crawl_jobs cj
                JOIN urls u ON cj.url_id = u.id
                WHERE cj.status = 'failed'
                GROUP BY u.domain
                ORDER BY count(*) DESC
                LIMIT 20
                """
            )
            stats["crawl_failures_by_domain"] = {
                row[0]: int(row[1]) for row in cur.fetchall()
            }

            cur.execute(
                """
                SELECT status, count(*)
                FROM score_jobs
                GROUP BY status
                ORDER BY status
                """
            )
            score_by_status = {row[0]: int(row[1]) for row in cur.fetchall()}
            stats["score_jobs_by_status"] = score_by_status
            score_total = sum(score_by_status.values())
            score_completed = score_by_status.get("completed", 0)
            score_failed = score_by_status.get("failed", 0)
            score_terminal = score_completed + score_failed
            stats["score_success_rate"] = (
                round(score_completed / score_terminal, 4) if score_terminal else None
            )

            cur.execute("SELECT count(*) FROM signal_snapshots")
            stats["signal_snapshots"] = int(cur.fetchone()[0])

            cur.execute("SELECT count(DISTINCT url_id) FROM signal_snapshots")
            stats["urls_with_snapshot"] = int(cur.fetchone()[0])

            cur.execute("SELECT count(*) FROM classifications")
            stats["classifications"] = int(cur.fetchone()[0])

            cur.execute("SELECT count(DISTINCT url_id) FROM classifications")
            stats["urls_with_classification"] = int(cur.fetchone()[0])

    stats["snapshot_coverage_pct"] = round(
        stats["urls_with_snapshot"] / gold_total * 100, 2
    ) if gold_total else 0.0
    stats["classification_coverage_pct"] = round(
        stats["urls_with_classification"] / gold_total * 100, 2
    ) if gold_total else 0.0
    return stats


def _pipeline_progress(db_url: str) -> dict[str, int]:
    """Return crawl/score counts for wait-loop progress (bottleneck is usually crawl)."""
    import psycopg

    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT status, count(*) FROM crawl_jobs GROUP BY status
                """
            )
            crawl = {row[0]: int(row[1]) for row in cur.fetchall()}
            cur.execute(
                """
                SELECT status, count(*) FROM score_jobs GROUP BY status
                """
            )
            score = {row[0]: int(row[1]) for row in cur.fetchall()}

    crawl_pending = crawl.get("queued", 0) + crawl.get("running", 0)
    score_pending = score.get("queued", 0) + score.get("running", 0)
    return {
        "crawl_completed": crawl.get("completed", 0),
        "crawl_failed": crawl.get("failed", 0),
        "crawl_pending": crawl_pending,
        "score_completed": score.get("completed", 0),
        "score_pending": score_pending,
        "pending_total": crawl_pending + score_pending,
    }


def _pending_jobs(db_url: str) -> int:
    return _pipeline_progress(db_url)["pending_total"]


def _ingest_gold_labels(api_url: str, source_batch_id: str, gold_labels_path: Path) -> dict:
    script = REPO_ROOT / "scripts" / "seed" / "ingest_gold_labels.py"
    cmd = [
        sys.executable,
        str(script),
        "--api-url",
        api_url,
        "--source-batch-id",
        source_batch_id,
        "--gold-labels",
        str(gold_labels_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False, cwd=REPO_ROOT)
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        raise RuntimeError(f"ingest failed with exit code {result.returncode}")
    print(result.stdout)
    return {"exit_code": result.returncode, "stdout": result.stdout}


def _wait_for_api(api_url: str, timeout_sec: int = 60) -> None:
    deadline = time.monotonic() + timeout_sec
    url = f"{api_url.rstrip('/')}/health"
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:
                if resp.status == 200:
                    return
        except (urllib.error.URLError, TimeoutError):
            time.sleep(2)
    raise TimeoutError(f"API not reachable at {api_url} within {timeout_sec}s")


def _wait_for_pipeline(
    db_url: str,
    *,
    timeout_sec: int,
    poll_interval_sec: int,
) -> dict:
    start = time.monotonic()
    last_pending = -1
    terminal_at_start: int | None = None
    while True:
        progress = _pipeline_progress(db_url)
        pending = progress["pending_total"]
        elapsed = int(time.monotonic() - start)
        terminal_now = progress["crawl_completed"] + progress["crawl_failed"]
        if terminal_at_start is None:
            terminal_at_start = terminal_now

        if pending != last_pending:
            eta_note = ""
            crawl_done_since_start = terminal_now - terminal_at_start
            if crawl_done_since_start > 0 and progress["crawl_pending"] > 0:
                sec_per_crawl = elapsed / crawl_done_since_start
                eta_min = int(progress["crawl_pending"] * sec_per_crawl / 60)
                eta_note = f", ~{eta_min}m crawl ETA (1 worker)"
            print(
                f"[{elapsed}s] pending={pending} "
                f"(crawl {progress['crawl_pending']} | score {progress['score_pending']}) "
                f"done crawl={progress['crawl_completed']}/{progress['crawl_failed']} fail "
                f"score={progress['score_completed']}{eta_note}"
            )
            last_pending = pending
        if pending == 0:
            return {"waited_sec": elapsed, "completed": True}
        if elapsed >= timeout_sec:
            return {"waited_sec": elapsed, "completed": False, "pending_jobs": pending}
        time.sleep(poll_interval_sec)


def _write_report(report: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
    print(f"\nWrote report to {path}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="POC-5.3 gold-label batch pipeline report")
    parser.add_argument(
        "--gold-labels",
        type=Path,
        default=DEFAULT_GOLD_LABELS,
    )
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=DEFAULT_ARTIFACT_DIR,
    )
    parser.add_argument(
        "--report-path",
        type=Path,
        default=DEFAULT_REPORT_PATH,
    )
    parser.add_argument(
        "--db-url",
        default=None,
        help="Sync Postgres URL (default: DATABASE_URL_SYNC or DATABASE_URL)",
    )
    parser.add_argument("--api-url", default="http://localhost:8000")
    parser.add_argument(
        "--source-batch-id",
        default="poc-5-batch-eval",
        help="source_batch_id for gold-label ingest",
    )
    parser.add_argument("--ingest", action="store_true", help="Ingest full gold-label set via API")
    parser.add_argument("--wait", action="store_true", help="Wait for crawl/score workers to finish")
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="Skip ingest/wait; report current pipeline state",
    )
    parser.add_argument("--timeout", type=int, default=7200, help="Max wait seconds (default 7200)")
    parser.add_argument("--poll-interval", type=int, default=15, help="Poll interval seconds")
    parser.add_argument("--skip-model-eval", action="store_true")
    return parser.parse_args()


def _print_empty_db_help() -> None:
    print(
        "\nNo crawled data in Postgres. Run the full pipeline first:\n"
        "  docker compose up -d\n"
        "  uv run --package mfa-ml python scripts/eval/batch_pipeline_report.py \\\n"
        "    --gold-labels data/seed/gold_labels_live.jsonl --ingest --wait\n"
        "\nOr report on existing DB state only:\n"
        "  uv run --package mfa-ml python scripts/eval/batch_pipeline_report.py --report-only\n",
        file=sys.stderr,
    )


def main() -> int:
    args = _parse_args()
    configure_logging(os.getenv("LOG_LEVEL", "INFO"))
    logger = structlog.get_logger(__name__)

    db_url = _sync_db_url(args.db_url)
    gold_total = _count_gold_labels(args.gold_labels)

    report: dict = {
        "generated_at": datetime.now(UTC).isoformat(),
        "gold_labels_path": str(args.gold_labels),
        "gold_label_total": gold_total,
        "db_url": db_url.split("@")[-1],  # omit credentials
    }

    if args.report_only:
        report["pipeline"] = _collect_pipeline_stats(db_url, gold_total)
        report["live_eval"] = evaluate_live_pipeline(db_url, args.gold_labels)
        if report["pipeline"].get("signal_snapshots", 0) == 0:
            _print_empty_db_help()
        if not args.skip_model_eval:
            report["model_eval"] = evaluate_model(
                db_url=db_url,
                gold_labels_path=args.gold_labels,
                artifact_dir=args.artifact_dir,
                eval_all=True,
            )
            if report["model_eval"].get("skipped_reason"):
                print(
                    f"NOTE: model eval skipped — {report['model_eval']['skipped_reason']}",
                    file=sys.stderr,
                )
        _write_report(report, args.report_path)
        return 0 if report["pipeline"].get("crawl_success_met") else 1

    if args.ingest:
        _wait_for_api(args.api_url)
        logger.info("ingest_start", gold_total=gold_total)
        report["ingest"] = _ingest_gold_labels(args.api_url, args.source_batch_id, args.gold_labels)

    if args.wait:
        logger.info("wait_start", timeout_sec=args.timeout)
        report["wait"] = _wait_for_pipeline(
            db_url,
            timeout_sec=args.timeout,
            poll_interval_sec=args.poll_interval,
        )
        if not report["wait"]["completed"]:
            print(
                f"WARNING: timed out with {report['wait'].get('pending_jobs', '?')} pending jobs",
                file=sys.stderr,
            )

    report["pipeline"] = _collect_pipeline_stats(db_url, gold_total)
    report["live_eval"] = evaluate_live_pipeline(db_url, args.gold_labels)

    if report["pipeline"].get("signal_snapshots", 0) == 0 and not args.ingest:
        _print_empty_db_help()

    if not args.skip_model_eval:
        report["model_eval"] = evaluate_model(
            db_url=db_url,
            gold_labels_path=args.gold_labels,
            artifact_dir=args.artifact_dir,
            eval_all=True,
        )
        if report["model_eval"].get("skipped_reason"):
            print(
                f"NOTE: model eval skipped — {report['model_eval']['skipped_reason']}",
                file=sys.stderr,
            )

    poc_exit = {
        "crawl_success_met": report["pipeline"].get("crawl_success_met", False),
        "live_precision_met": report["live_eval"]["poc_targets"]["precision_met"],
        "live_recall_met": report["live_eval"]["poc_targets"]["recall_met"],
        "metrics_documented": True,
    }
    report["poc_exit"] = poc_exit
    _write_report(report, args.report_path)

    _print_summary(report)
    return 0 if poc_exit["crawl_success_met"] else 1


def _print_summary(report: dict) -> None:
    pipeline = report.get("pipeline", {})
    live = report.get("live_eval", {})
    print("\n" + "=" * 60)
    print("BATCH PIPELINE REPORT")
    print("=" * 60)
    print(f"Gold labels     : {report.get('gold_label_total')}")
    print(f"URLs in DB      : {pipeline.get('urls_in_db')}")
    print(f"Crawl jobs      : {pipeline.get('crawl_jobs_by_status')}")
    rate = pipeline.get("crawl_success_rate")
    print(
        f"Crawl success   : {rate:.1%} (target ≥ {CRAWL_SUCCESS_TARGET:.0%})"
        if rate is not None
        else "Crawl success   : n/a"
    )
    print(f"Snapshots       : {pipeline.get('signal_snapshots')} ({pipeline.get('snapshot_coverage_pct')}%)")
    print(f"Classifications : {pipeline.get('classifications')} ({pipeline.get('classification_coverage_pct')}%)")
    if live:
        print(f"Live precision  : {live.get('precision', 0):.1%}")
        print(f"Live recall     : {live.get('recall', 0):.1%}")
    print("=" * 60)


if __name__ == "__main__":
    raise SystemExit(main())
