"""OpenSearch index mapping for RAG v1 (MVP-3.1)."""

from __future__ import annotations

INDEX_NAME = "mfa-rag-v1"

INDEX_BODY = {
    "settings": {
        "index": {
            "number_of_shards": 1,
            "number_of_replicas": 0,
        }
    },
    "mappings": {
        "properties": {
            "chunk_id": {"type": "keyword"},
            "doc_type": {"type": "keyword"},
            "domain": {"type": "keyword"},
            "url_id": {"type": "keyword"},
            "url": {"type": "text"},
            "tier": {"type": "keyword"},
            "excerpt": {"type": "text"},
            "content": {"type": "object", "enabled": False},
            "evidence_hash": {"type": "keyword"},
            "indexed_at": {"type": "date"},
        }
    },
}
