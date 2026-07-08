"""Score queue consumer — polls Postgres score_jobs and writes classifications."""

from __future__ import annotations

import asyncio
import os
import signal
import sys
from pathlib import Path

import structlog
from mfa_common.logging import configure_logging
from mfa_ml.consumer import run_consumer_loop
from mfa_ml.scoring.artifact_loader import load_scoring_artifacts

logger = structlog.get_logger(__name__)


def _artifact_dir() -> Path:
    return Path(os.getenv("ARTIFACT_DIR", "ml/artifacts/v1"))


def _run() -> None:
    shutdown = asyncio.Event()
    artifacts = load_scoring_artifacts(_artifact_dir())

    def _request_shutdown(signum: int, _frame: object) -> None:
        logger.info("ml_worker_shutting_down", signal=signum)
        shutdown.set()

    signal.signal(signal.SIGTERM, _request_shutdown)
    signal.signal(signal.SIGINT, _request_shutdown)

    logger.info("ml_worker_ready", env=os.getenv("ENV", "local"), artifact_dir=str(_artifact_dir()))
    asyncio.run(run_consumer_loop(artifacts=artifacts, shutdown_event=shutdown))


def main() -> None:
    configure_logging(os.getenv("LOG_LEVEL", "INFO"))
    try:
        _run()
    except KeyboardInterrupt:
        logger.info("ml_worker_interrupted")
        sys.exit(0)


if __name__ == "__main__":
    main()
