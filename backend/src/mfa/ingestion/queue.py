import uuid
from dataclasses import dataclass
from typing import Protocol

from mfa.ingestion.sqs_transport import publish_crawl_job


@dataclass(frozen=True)
class CrawlJobMessage:
    job_id: uuid.UUID
    url_id: uuid.UUID
    normalized_url: str
    priority: int


class QueueBackend(Protocol):
    async def enqueue_crawl(self, message: CrawlJobMessage) -> None: ...


class InMemoryQueue:
    """In-process queue retained for API tests and local introspection.

    Workers consume jobs via Postgres poll or SQS (MVP-1.3). Postgres ``crawl_jobs``
    remains the durable source of truth; SQS is the worker notification channel.
    """

    def __init__(self) -> None:
        self.messages: list[CrawlJobMessage] = []

    async def enqueue_crawl(self, message: CrawlJobMessage) -> None:
        self.messages.append(message)


class SqsQueueBackend:
    """Publish crawl jobs to SQS batch or FIFO priority queue (MVP-1.3)."""

    def __init__(self) -> None:
        from mfa.ingestion.sqs_transport import sqs_enabled

        self._enabled = sqs_enabled()

    @property
    def enabled(self) -> bool:
        return self._enabled

    async def enqueue_crawl(self, message: CrawlJobMessage) -> None:
        if not self.enabled:
            return
        publish_crawl_job(
            job_id=message.job_id,
            url_id=message.url_id,
            normalized_url=message.normalized_url,
            priority=message.priority,
        )


_queue: QueueBackend | None = None


def get_queue() -> QueueBackend:
    global _queue
    if _queue is None:
        from mfa.ingestion.sqs_transport import sqs_enabled

        _queue = SqsQueueBackend() if sqs_enabled() else InMemoryQueue()
    return _queue


def set_queue(queue: QueueBackend) -> None:
    global _queue
    _queue = queue
