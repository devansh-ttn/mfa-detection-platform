"""OpenSearch client — hybrid BM25 search (MVP-3.1)."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

import structlog

from mfa.rag.opensearch_mappings import INDEX_BODY, INDEX_NAME
from mfa.rag.schemas import EvidenceChunk

logger = structlog.get_logger(__name__)


class OpenSearchClient:
    def __init__(self) -> None:
        self.endpoint = os.getenv("OPENSEARCH_ENDPOINT", "").rstrip("/")
        self.index = os.getenv("OPENSEARCH_INDEX", INDEX_NAME)
        self.enabled = bool(self.endpoint)
        self._client: Any | None = None

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        from opensearchpy import OpenSearch

        use_ssl = self.endpoint.startswith("https")
        self._client = OpenSearch(
            hosts=[self.endpoint],
            use_ssl=use_ssl,
            verify_certs=use_ssl and os.getenv("OPENSEARCH_VERIFY_CERTS", "true").lower()
            not in {"0", "false", "no"},
            http_auth=self._http_auth(),
        )
        return self._client

    def _http_auth(self) -> tuple[str, str] | None:
        user = os.getenv("OPENSEARCH_USER", "")
        password = os.getenv("OPENSEARCH_PASSWORD", "")
        if user and password:
            return user, password
        return None

    def ensure_index(self) -> None:
        if not self.enabled:
            return
        client = self._get_client()
        if not client.indices.exists(index=self.index):
            client.indices.create(index=self.index, body=INDEX_BODY)
            logger.info("opensearch_index_created", index=self.index)

    def index_document(self, doc: dict[str, Any], *, doc_id: str) -> None:
        if not self.enabled:
            return
        self.ensure_index()
        self._get_client().index(index=self.index, id=doc_id, body=doc, refresh=False)

    def search(
        self,
        query: str,
        *,
        filters: dict[str, Any] | None = None,
        k: int = 5,
    ) -> list[EvidenceChunk]:
        if not self.enabled or not query.strip():
            return []

        must: list[dict[str, Any]] = [
            {
                "multi_match": {
                    "query": query,
                    "fields": ["excerpt^2", "url", "domain"],
                    "type": "best_fields",
                }
            }
        ]
        filter_clauses: list[dict[str, Any]] = []
        if filters:
            for key, value in filters.items():
                if value is not None:
                    filter_clauses.append({"term": {key: value}})

        body: dict[str, Any] = {
            "size": k,
            "query": {
                "bool": {
                    "must": must,
                    "filter": filter_clauses,
                }
            },
        }

        try:
            response = self._get_client().search(index=self.index, body=body)
        except Exception:
            logger.exception("opensearch_search_failed")
            return []

        chunks: list[EvidenceChunk] = []
        for hit in response.get("hits", {}).get("hits", []):
            source = hit.get("_source", {})
            chunk_id = str(source.get("chunk_id", hit.get("_id", "")))
            chunks.append(
                EvidenceChunk(
                    chunk_id=chunk_id,
                    doc_type=str(source.get("doc_type", "unknown")),
                    content=dict(source.get("content") or {}),
                    excerpt=str(source.get("excerpt", ""))[:500],
                )
            )
        return chunks


@lru_cache
def get_opensearch_client() -> OpenSearchClient:
    return OpenSearchClient()
