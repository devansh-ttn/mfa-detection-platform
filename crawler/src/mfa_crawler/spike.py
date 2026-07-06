"""100-domain crawler spike — success rate, crawl timing, DOM metric distributions."""

from __future__ import annotations

import asyncio
import json
import statistics
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog
from mfa_crawler.crawl import crawl_url
from mfa_crawler.dom_parser import CORE_DOM_METRIC_NAMES
from mfa_crawler.spike_data import SpikeTarget, load_spike_targets

logger = structlog.get_logger(__name__)

SPIKE_REPORT_VERSION = "crawl_spike_v1"


@dataclass(frozen=True)
class SpikeCrawlSuccess:
    target: SpikeTarget
    url: str
    duration_sec: float
    metrics: dict[str, Any]


@dataclass(frozen=True)
class SpikeCrawlFailure:
    target: SpikeTarget
    error: str


def _metric_summary(values: list[float]) -> dict[str, float | int | None]:
    if not values:
        return {"count": 0, "median": None, "p95": None, "min": None, "max": None, "mean": None}
    return {
        "count": len(values),
        "median": round(statistics.median(values), 4),
        "p95": round(statistics.quantiles(values, n=20)[18], 4) if len(values) > 1 else values[0],
        "min": round(min(values), 4),
        "max": round(max(values), 4),
        "mean": round(statistics.fmean(values), 4),
    }


def _duration_summary(durations: list[float]) -> dict[str, float | int | None]:
    return _metric_summary(durations)


def _group_by_label(
    successes: list[SpikeCrawlSuccess],
    failures: list[SpikeCrawlFailure],
) -> dict[str, dict[str, int | float | None]]:
    labels = {item.target.primary_gold_label for item in successes} | {
        item.target.primary_gold_label for item in failures
    }
    grouped: dict[str, dict[str, int | float | None]] = {}
    for label in sorted(labels):
        label_successes = [item for item in successes if item.target.primary_gold_label == label]
        label_failures = [item for item in failures if item.target.primary_gold_label == label]
        attempted = len(label_successes) + len(label_failures)
        succeeded = len(label_successes)
        grouped[label] = {
            "attempted": attempted,
            "succeeded": succeeded,
            "failed": len(label_failures),
            "success_rate": round(succeeded / attempted, 4) if attempted else None,
            "median_crawl_duration_sec": _duration_summary(
                [item.duration_sec for item in label_successes]
            )["median"],
        }
    return grouped


def build_spike_report(
    *,
    targets: list[SpikeTarget],
    successes: list[SpikeCrawlSuccess],
    failures: list[SpikeCrawlFailure],
    delay_sec: float,
) -> dict[str, Any]:
    attempted = len(targets)
    succeeded = len(successes)
    durations = [item.duration_sec for item in successes]

    metric_summaries: dict[str, dict[str, float | int | None]] = {}
    for metric_name in CORE_DOM_METRIC_NAMES:
        values: list[float] = []
        for item in successes:
            raw = item.metrics.get(metric_name)
            if raw is not None:
                values.append(float(raw))
        metric_summaries[metric_name] = _metric_summary(values)

    top_by_median = sorted(
        (
            (name, summary["median"])
            for name, summary in metric_summaries.items()
            if summary["median"] is not None
        ),
        key=lambda pair: pair[1],
        reverse=True,
    )

    return {
        "schema_version": SPIKE_REPORT_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "domain_count": len(targets),
        "attempted": attempted,
        "succeeded": succeeded,
        "failed": len(failures),
        "success_rate": round(succeeded / attempted, 4) if attempted else 0.0,
        "delay_sec_between_crawls": delay_sec,
        "crawl_duration_sec": _duration_summary(durations),
        "metrics": metric_summaries,
        "top_metrics_by_median": [
            {"metric": name, "median": median} for name, median in top_by_median[:5]
        ],
        "by_primary_gold_label": _group_by_label(successes, failures),
        "failures": [
            {
                "domain": item.target.domain,
                "candidate_urls": list(item.target.candidate_urls),
                "primary_gold_label": item.target.primary_gold_label,
                "error": item.error,
            }
            for item in failures
        ],
    }


def render_spike_report_markdown(report: dict[str, Any]) -> str:
    duration = report["crawl_duration_sec"]
    lines = [
        "# Crawler spike report",
        "",
        f"- Generated: `{report['generated_at']}`",
        f"- Domains: **{report['domain_count']}**",
        f"- Success rate: **{report['success_rate']:.1%}** "
        f"({report['succeeded']}/{report['attempted']})",
        f"- Median crawl time: **{duration['median']}s**",
        f"- P95 crawl time: **{duration['p95']}s**",
        "",
        "## Top DOM metrics (median)",
        "",
        "| Metric | Median | P95 |",
        "|--------|--------|-----|",
    ]
    for entry in report["top_metrics_by_median"]:
        metric = entry["metric"]
        summary = report["metrics"][metric]
        lines.append(f"| `{metric}` | {summary['median']} | {summary['p95']} |")

    lines.extend(["", "## By gold label", "", "| Label | Attempted | Success rate | Median crawl (s) |", "|-------|-----------|--------------|------------------|"])
    for label, stats in report["by_primary_gold_label"].items():
        rate = stats["success_rate"]
        rate_display = f"{rate:.1%}" if rate is not None else "n/a"
        lines.append(
            f"| `{label}` | {stats['attempted']} | {rate_display} | {stats['median_crawl_duration_sec']} |"
        )

    if report["failures"]:
        lines.extend(["", "## Failures", ""])
        for failure in report["failures"]:
            lines.append(f"- `{failure['domain']}` — {failure['error']}")

    return "\n".join(lines) + "\n"


async def _crawl_target_with_fallback(target: SpikeTarget) -> SpikeCrawlSuccess:
    errors: list[str] = []
    for url in target.candidate_urls:
        try:
            result = await crawl_url(url)
            metrics = result.payload.features.model_dump(mode="json")
            return SpikeCrawlSuccess(
                target=target,
                url=url,
                duration_sec=result.duration_sec,
                metrics=metrics,
            )
        except Exception as exc:
            errors.append(f"{url}: {exc}")
    raise RuntimeError("; ".join(errors))


async def run_spike(
    *,
    domain_limit: int = 100,
    delay_sec: float = 1.0,
) -> dict[str, Any]:
    targets = load_spike_targets(domain_limit=domain_limit)
    successes: list[SpikeCrawlSuccess] = []
    failures: list[SpikeCrawlFailure] = []

    logger.info("crawl_spike_started", domain_count=len(targets), delay_sec=delay_sec)

    for index, target in enumerate(targets, start=1):
        logger.info(
            "crawl_spike_target",
            index=index,
            total=len(targets),
            domain=target.domain,
            candidate_urls=len(target.candidate_urls),
        )
        try:
            success = await _crawl_target_with_fallback(target)
            successes.append(success)
        except Exception as exc:
            logger.warning(
                "crawl_spike_target_failed",
                domain=target.domain,
                error=str(exc),
            )
            failures.append(SpikeCrawlFailure(target=target, error=str(exc)))

        if index < len(targets) and delay_sec > 0:
            await asyncio.sleep(delay_sec)

    report = build_spike_report(
        targets=targets,
        successes=successes,
        failures=failures,
        delay_sec=delay_sec,
    )
    logger.info(
        "crawl_spike_finished",
        success_rate=report["success_rate"],
        median_crawl_sec=report["crawl_duration_sec"]["median"],
    )
    return report


def write_spike_report(report: dict[str, Any], output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "report.json"
    md_path = output_dir / "report.md"
    json_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    md_path.write_text(render_spike_report_markdown(report), encoding="utf-8")
    return json_path, md_path
