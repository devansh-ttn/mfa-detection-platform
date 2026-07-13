"""Unit tests for SQS transport helpers (MVP-1.3)."""

from __future__ import annotations

import json
import uuid
from unittest.mock import MagicMock, patch

import pytest

from mfa.ingestion.sqs_transport import (
    crawl_queue_url,
    publish_crawl_job,
    receive_job_messages,
    sqs_enabled,
)


def test_sqs_disabled_without_env(monkeypatch) -> None:
    monkeypatch.delenv("SQS_CRAWL_QUEUE_URL", raising=False)
    monkeypatch.delenv("SQS_BATCH_QUEUE_URL", raising=False)
    monkeypatch.delenv("SQS_SCORE_QUEUE_URL", raising=False)
    assert sqs_enabled() is False


def test_crawl_queue_routes_priority(monkeypatch) -> None:
    monkeypatch.setenv("SQS_BATCH_QUEUE_URL", "https://sqs/batch")
    monkeypatch.setenv("SQS_PRIORITY_QUEUE_URL", "https://sqs/priority.fifo")
    assert crawl_queue_url(priority=0) == "https://sqs/batch"
    assert crawl_queue_url(priority=5) == "https://sqs/priority.fifo"


@patch("mfa.ingestion.sqs_transport._sqs_client")
def test_publish_crawl_job(mock_client_factory, monkeypatch) -> None:
    monkeypatch.setenv("SQS_BATCH_QUEUE_URL", "https://sqs/batch")
    client = MagicMock()
    mock_client_factory.return_value = client
    job_id = uuid.uuid4()
    url_id = uuid.uuid4()
    publish_crawl_job(
        job_id=job_id,
        url_id=url_id,
        normalized_url="https://example.com",
        priority=0,
    )
    client.send_message.assert_called_once()
    body = json.loads(client.send_message.call_args.kwargs["MessageBody"])
    assert body["type"] == "crawl"
    assert body["job_id"] == str(job_id)


@patch("mfa.ingestion.sqs_transport._sqs_client")
def test_receive_job_messages_parses_crawl(mock_client_factory, monkeypatch) -> None:
    monkeypatch.setenv("SQS_BATCH_QUEUE_URL", "https://sqs/batch")
    job_id = uuid.uuid4()
    url_id = uuid.uuid4()
    client = MagicMock()
    mock_client_factory.return_value = client
    client.receive_message.return_value = {
        "Messages": [
            {
                "ReceiptHandle": "rh-1",
                "Body": json.dumps(
                    {
                        "type": "crawl",
                        "job_id": str(job_id),
                        "url_id": str(url_id),
                        "normalized_url": "https://example.com",
                        "priority": 0,
                    }
                ),
            }
        ]
    }
    messages = receive_job_messages(["https://sqs/batch"])
    assert len(messages) == 1
    assert messages[0].job_type == "crawl"
    assert messages[0].job_id == job_id
    assert messages[0].receipt_handle == "rh-1"
