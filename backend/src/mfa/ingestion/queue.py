import uuid
from dataclasses import dataclass
from typing import Protocol


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

    The crawler-worker consumes jobs by polling Postgres (`job_poll.py`), not this
    queue. TODO(MVP): replace with SQS per docs/ROADMAP.md (MVP-1.3).
    """

    def __init__(self) -> None:
        self.messages: list[CrawlJobMessage] = []

    async def enqueue_crawl(self, message: CrawlJobMessage) -> None:
        self.messages.append(message)


_queue: QueueBackend | None = None


def get_queue() -> QueueBackend:
    global _queue
    if _queue is None:
        _queue = InMemoryQueue()
    return _queue


def set_queue(queue: QueueBackend) -> None:
    global _queue
    _queue = queue
