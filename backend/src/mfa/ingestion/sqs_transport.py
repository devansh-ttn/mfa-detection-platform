"""SQS transport helpers for crawl and score job consumers (MVP-1.3)."""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass
from typing import Any, Literal

import structlog

logger = structlog.get_logger(__name__)

JobType = Literal["crawl", "score"]


@dataclass(frozen=True)
class SqsJobMessage:
    job_type: JobType
    job_id: uuid.UUID
    url_id: uuid.UUID
    receipt_handle: str
    signal_snapshot_id: uuid.UUID | None = None
    normalized_url: str | None = None
    priority: int = 0


def _sqs_client():
    import boto3

    return boto3.client(
        "sqs",
        region_name=os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
        endpoint_url=os.getenv("AWS_ENDPOINT_URL") or None,
    )


def crawl_queue_url(*, priority: int = 0) -> str:
    """Route to FIFO priority queue when priority > 0, else batch queue."""
    if priority > 0:
        return os.getenv("SQS_PRIORITY_QUEUE_URL", "")
    return os.getenv("SQS_CRAWL_QUEUE_URL", "") or os.getenv("SQS_BATCH_QUEUE_URL", "")


def score_queue_url() -> str:
    return os.getenv("SQS_SCORE_QUEUE_URL", "") or os.getenv("SQS_BATCH_QUEUE_URL", "")


def sqs_enabled() -> bool:
    return bool(
        os.getenv("SQS_CRAWL_QUEUE_URL")
        or os.getenv("SQS_BATCH_QUEUE_URL")
        or os.getenv("SQS_SCORE_QUEUE_URL")
    )


def publish_message(
    queue_url: str,
    body: dict[str, Any],
    *,
    message_group_id: str | None = None,
) -> None:
    if not queue_url:
        return
    client = _sqs_client()
    kwargs: dict[str, Any] = {
        "QueueUrl": queue_url,
        "MessageBody": json.dumps(body),
    }
    if message_group_id:
        kwargs["MessageGroupId"] = message_group_id
        kwargs["MessageDeduplicationId"] = str(body.get("job_id", uuid.uuid4()))
    client.send_message(**kwargs)
    logger.debug("sqs_message_published", queue_url=queue_url, job_type=body.get("type"))


def publish_crawl_job(
    *,
    job_id: uuid.UUID,
    url_id: uuid.UUID,
    normalized_url: str,
    priority: int,
) -> None:
    queue_url = crawl_queue_url(priority=priority)
    if not queue_url:
        return
    body = {
        "type": "crawl",
        "job_id": str(job_id),
        "url_id": str(url_id),
        "normalized_url": normalized_url,
        "priority": priority,
    }
    group_id = str(url_id) if priority > 0 else None
    publish_message(queue_url, body, message_group_id=group_id)


def publish_score_job(
    *,
    job_id: uuid.UUID,
    url_id: uuid.UUID,
    signal_snapshot_id: uuid.UUID,
    priority: int = 0,
) -> None:
    queue_url = score_queue_url()
    if not queue_url:
        return
    body = {
        "type": "score",
        "job_id": str(job_id),
        "url_id": str(url_id),
        "signal_snapshot_id": str(signal_snapshot_id),
        "priority": priority,
    }
    publish_message(queue_url, body)


def _parse_body(body: dict[str, Any], receipt_handle: str) -> SqsJobMessage | None:
    job_type = body.get("type")
    if job_type not in {"crawl", "score"}:
        return None
    try:
        job_id = uuid.UUID(str(body["job_id"]))
        url_id = uuid.UUID(str(body["url_id"]))
    except (KeyError, ValueError):
        return None

    snapshot_id: uuid.UUID | None = None
    if body.get("signal_snapshot_id"):
        try:
            snapshot_id = uuid.UUID(str(body["signal_snapshot_id"]))
        except ValueError:
            return None

    return SqsJobMessage(
        job_type=job_type,  # type: ignore[arg-type]
        job_id=job_id,
        url_id=url_id,
        receipt_handle=receipt_handle,
        signal_snapshot_id=snapshot_id,
        normalized_url=body.get("normalized_url"),
        priority=int(body.get("priority", 0)),
    )


def receive_job_messages(
    queue_urls: list[str],
    *,
    max_messages: int = 1,
    wait_seconds: int = 5,
) -> list[SqsJobMessage]:
    """Long-poll one or more queues; returns parsed job messages."""
    client = _sqs_client()
    results: list[SqsJobMessage] = []

    for queue_url in queue_urls:
        if not queue_url:
            continue
        response = client.receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=max_messages,
            WaitTimeSeconds=wait_seconds,
            MessageAttributeNames=["All"],
        )
        for raw in response.get("Messages", []):
            try:
                body = json.loads(raw["Body"])
            except (json.JSONDecodeError, KeyError):
                logger.warning("sqs_invalid_message_body", queue_url=queue_url)
                continue
            parsed = _parse_body(body, raw["ReceiptHandle"])
            if parsed:
                results.append(parsed)
            if len(results) >= max_messages:
                return results
    return results


def delete_message(queue_url: str, receipt_handle: str) -> None:
    if not queue_url or not receipt_handle:
        return
    _sqs_client().delete_message(QueueUrl=queue_url, ReceiptHandle=receipt_handle)


def resolve_queue_for_message(msg: SqsJobMessage) -> str:
    if msg.job_type == "score":
        return score_queue_url()
    return crawl_queue_url(priority=msg.priority)
