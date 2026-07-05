"""POC stub — crawl queue consumer (Phase 3: Playwright integration)."""

from __future__ import annotations

import os
import signal
import sys
import time

import structlog
from mfa_common.logging import configure_logging

logger = structlog.get_logger(__name__)


def _shutdown(_signum: int, _frame: object) -> None:
    logger.info("crawler_worker_shutting_down", signal=_signum)
    sys.exit(0)


def main() -> None:
    configure_logging(os.getenv("LOG_LEVEL", "INFO"))
    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    logger.info("crawler_worker_stub_ready", env=os.getenv("ENV", "poc"))

    while True:
        time.sleep(30)


if __name__ == "__main__":
    main()
