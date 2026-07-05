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
    """POC queue — replaced by SQS in MVP."""

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
