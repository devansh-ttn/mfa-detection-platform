"""Tests for OpenSearch indexing document builders."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from mfa.db.models import Classification, SignalSnapshot, Url
from mfa.rag.indexer import _base_doc


def test_base_doc_shape() -> None:
    url = Url(
        id=uuid.uuid4(),
        url="https://example.com/page",
        normalized_url="https://example.com/page",
        url_hash="abc",
        domain="example.com",
    )
    doc = _base_doc(
        chunk_id="classification:1",
        doc_type="explanation",
        url=url,
        excerpt="High ad density",
        content={"tier": "MFA_High"},
        evidence_hash="hash1",
        tier="MFA_High",
    )
    assert doc["chunk_id"] == "classification:1"
    assert doc["domain"] == "example.com"
    assert doc["evidence_hash"] == "hash1"
    assert "indexed_at" in doc
