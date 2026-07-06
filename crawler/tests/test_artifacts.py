"""Tests for local evidence artifact storage."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from mfa_crawler.artifacts import (
    DOM_METRICS_FILENAME,
    HTML_FILENAME,
    SCREENSHOT_FILENAME,
    evidence_artifact_dir,
    write_evidence_artifacts,
)


def test_write_evidence_artifacts_creates_expected_files(tmp_path: Path) -> None:
    url_id = uuid.uuid4()
    dom_metrics = {"ad_slots_count": 2, "content_word_count": 100}

    target = write_evidence_artifacts(
        url_id=url_id,
        version=1,
        html="<html><body>test</body></html>",
        screenshot_png=b"\x89PNG\r\n",
        dom_metrics=dom_metrics,
        base_dir=tmp_path,
    )

    assert target == evidence_artifact_dir(url_id, 1, base_dir=tmp_path)
    assert (target / HTML_FILENAME).read_text(encoding="utf-8") == "<html><body>test</body></html>"
    assert (target / SCREENSHOT_FILENAME).read_bytes() == b"\x89PNG\r\n"
    saved_metrics = json.loads((target / DOM_METRICS_FILENAME).read_text(encoding="utf-8"))
    assert saved_metrics == dom_metrics
