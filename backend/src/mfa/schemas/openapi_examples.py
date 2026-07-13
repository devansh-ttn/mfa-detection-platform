"""Shared OpenAPI request/response examples for v1 endpoints."""

from __future__ import annotations

from datetime import UTC, datetime

_URL_ID = "550e8400-e29b-41d4-a716-446655440001"
_JOB_ID = "550e8400-e29b-41d4-a716-446655440002"
_CLASSIFICATION_ID = "550e8400-e29b-41d4-a716-446655440003"
_SNAPSHOT_ID = "550e8400-e29b-41d4-a716-446655440004"
_EVIDENCE_HASH = "a" * 64
_TS = datetime(2026, 7, 8, 12, 0, 0, tzinfo=UTC).isoformat()

URL_SUBMIT_REQUEST = {
    "urls": ["https://example.com/article", "https://news.example.org/story"],
    "source_batch_id": "gold-label-batch-001",
    "priority": 1,
}

URL_SUBMIT_RESPONSE = {
    "jobs": [
        {
            "job_id": _JOB_ID,
            "url_id": _URL_ID,
            "normalized_url": "https://example.com/article",
            "status": "queued",
            "idempotency_key": "abc123:gold-label-batch-001",
            "duplicate": False,
        }
    ],
    "accepted": 1,
    "duplicate": 0,
    "invalid": [],
}

JOB_RESPONSE = {
    "job_id": _JOB_ID,
    "url_id": _URL_ID,
    "status": "completed",
    "url": "https://example.com/article",
    "normalized_url": "https://example.com/article",
    "domain": "example.com",
    "priority": 1,
    "source_batch_id": "gold-label-batch-001",
    "error_message": None,
    "created_at": _TS,
    "updated_at": _TS,
}

SIGNAL_SNAPSHOT_RESPONSE = {
    "snapshot_id": _SNAPSHOT_ID,
    "url_id": _URL_ID,
    "version": 1,
    "signals": {
        "schema_version": "v1",
        "crawl_ts": _TS,
        "ad_to_content_ratio": 0.42,
        "ads_above_fold": 3,
        "ad_slots_count": 8,
        "sticky_ad_count": 2,
        "content_word_count": 450,
    },
    "evidence_hash": _EVIDENCE_HASH,
    "persona": "direct",
    "crawl_duration_sec": 12.5,
    "created_at": _TS,
}

CLASSIFICATION_RESPONSE = {
    "classification_id": _CLASSIFICATION_ID,
    "url_id": _URL_ID,
    "signal_snapshot_id": _SNAPSHOT_ID,
    "tier": "MFA_Medium",
    "mfa_score": 0.72,
    "confidence": "medium",
    "top_signals": [
        {
            "feature": "ad_to_content_ratio",
            "value": 0.42,
            "contribution": 0.31,
            "rank": 1,
        }
    ],
    "explanation": "Elevated ad-to-content ratio (0.42) suggests MFA characteristics.",
    "evidence_hash": _EVIDENCE_HASH,
    "classifier": "xgboost",
    "schema_version": "v1",
    "created_at": _TS,
}

CLASSIFICATION_INDEX_ITEM = {
    **CLASSIFICATION_RESPONSE,
    "url": "https://example.com/article",
    "domain": "example.com",
}

CLASSIFICATION_INDEX_RESPONSE = {
    "classifications": [CLASSIFICATION_INDEX_ITEM],
    "total": 1,
    "limit": 50,
    "offset": 0,
}

CLASSIFICATION_HISTORY_RESPONSE = {
    "url_id": _URL_ID,
    "classifications": [CLASSIFICATION_RESPONSE],
    "total": 1,
    "limit": 20,
    "offset": 0,
}

SIGNAL_LIST_RESPONSE = {
    "url_id": _URL_ID,
    "snapshots": [SIGNAL_SNAPSHOT_RESPONSE],
    "total": 1,
    "limit": 20,
    "offset": 0,
}
