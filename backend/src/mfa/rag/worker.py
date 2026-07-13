"""OpenSearch indexing worker loop (MVP-3.2)."""

from __future__ import annotations

import asyncio
import os
import signal
import sys

import structlog
from mfa.db.session import async_session_factory
from mfa.rag.indexer import index_recent_entities
from mfa.rag.opensearch_client import get_opensearch_client
from mfa_common.logging import configure_logging

logger = structlog.get_logger(__name__)


def load_poll_interval_sec() -> float:
    return float(os.getenv("INDEX_POLL_INTERVAL_SEC", "30"))


async def run_indexer_loop(*, shutdown_event: asyncio.Event | None = None) -> None:
    client = get_opensearch_client()
    if not client.enabled:
        logger.warning("indexer_disabled", reason="OPENSEARCH_ENDPOINT unset")
        return

    interval = load_poll_interval_sec()
    stop = shutdown_event or asyncio.Event()
    logger.info("indexer_worker_started", poll_interval_sec=interval)

    while not stop.is_set():
        try:
            async with async_session_factory() as session:
                count = await index_recent_entities(session, limit=50)
                if count:
                    await session.commit()
        except Exception:
            logger.exception("indexer_loop_error")

        try:
            await asyncio.wait_for(stop.wait(), timeout=interval)
        except TimeoutError:
            continue

    logger.info("indexer_worker_stopped")


def main() -> None:
    configure_logging(os.getenv("LOG_LEVEL", "INFO"))
    shutdown = asyncio.Event()

    def _request_shutdown(signum: int, _frame: object) -> None:
        logger.info("indexer_worker_shutting_down", signal=signum)
        shutdown.set()

    signal.signal(signal.SIGTERM, _request_shutdown)
    signal.signal(signal.SIGINT, _request_shutdown)

    try:
        asyncio.run(run_indexer_loop(shutdown_event=shutdown))
    except KeyboardInterrupt:
        logger.info("indexer_worker_interrupted")
        sys.exit(0)


if __name__ == "__main__":
    main()
