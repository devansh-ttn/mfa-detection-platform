"""Local evidence artifact storage for crawl results."""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

SCREENSHOT_FILENAME = "screenshot.png"
HTML_FILENAME = "page.html"
DOM_METRICS_FILENAME = "dom_metrics.json"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def resolve_evidence_dir() -> Path:
    """Return the root directory for evidence artifacts."""
    configured = os.getenv("EVIDENCE_DIR")
    if configured:
        return Path(configured)
    return _repo_root() / "backend" / "evidence"


def evidence_artifact_dir(url_id: uuid.UUID, version: int, *, base_dir: Path | None = None) -> Path:
    root = base_dir or resolve_evidence_dir()
    return root / str(url_id) / str(version)


def write_evidence_artifacts(
    *,
    url_id: uuid.UUID,
    version: int,
    html: str,
    screenshot_png: bytes,
    dom_metrics: dict[str, Any],
    base_dir: Path | None = None,
) -> Path:
    """Write screenshot, HTML, and dom_metrics.json under {url_id}/{version}/."""
    target = evidence_artifact_dir(url_id, version, base_dir=base_dir)
    target.mkdir(parents=True, exist_ok=True)

    (target / SCREENSHOT_FILENAME).write_bytes(screenshot_png)
    (target / HTML_FILENAME).write_text(html, encoding="utf-8")
    (target / DOM_METRICS_FILENAME).write_text(
        json.dumps(dom_metrics, indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )

    logger.info(
        "evidence_artifacts_written",
        url_id=str(url_id),
        version=version,
        artifact_dir=str(target),
    )
    return target
