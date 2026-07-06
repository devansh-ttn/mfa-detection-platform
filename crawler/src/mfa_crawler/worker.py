"""Crawl queue consumer — polls Postgres crawl_jobs and runs Playwright crawls."""

from __future__ import annotations

import asyncio
import os
import signal
import sys

import structlog
from mfa_common.logging import configure_logging

from mfa_crawler.consumer import run_consumer_loop

logger = structlog.get_logger(__name__)


def _run() -> None:
    shutdown = asyncio.Event()

    def _request_shutdown(signum: int, _frame: object) -> None:
        logger.info("crawler_worker_shutting_down", signal=signum)
        shutdown.set()

    signal.signal(signal.SIGTERM, _request_shutdown)
    signal.signal(signal.SIGINT, _request_shutdown)

    logger.info("crawler_worker_ready", env=os.getenv("ENV", "local"))
    asyncio.run(run_consumer_loop(shutdown_event=shutdown))


def main() -> None:
    configure_logging(os.getenv("LOG_LEVEL", "INFO"))
    try:
        _run()
    except KeyboardInterrupt:
        logger.info("crawler_worker_interrupted")
        sys.exit(0)


if __name__ == "__main__":
    main()
