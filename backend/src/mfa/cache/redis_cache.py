"""Redis cache for domain tier lookups (MVP-1.6)."""

from __future__ import annotations

import json
import os
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

_CACHE_TTL_SEC = int(os.getenv("REDIS_CACHE_TTL_SEC", "86400"))


class DomainTierCache:
    """Cache latest classification tier per domain with evidence_hash binding."""

    def __init__(self, redis_url: str | None = None) -> None:
        self._redis_url = redis_url or os.getenv("REDIS_URL", "")
        self._client: Any | None = None

    @property
    def enabled(self) -> bool:
        return bool(self._redis_url)

    def _get_client(self) -> Any:
        if self._client is None:
            import redis

            self._client = redis.from_url(self._redis_url, decode_responses=True)
        return self._client

    def _key(self, domain: str) -> str:
        return f"domain:{domain}:tier"

    def get(self, domain: str) -> dict[str, Any] | None:
        if not self.enabled:
            return None
        try:
            raw = self._get_client().get(self._key(domain))
            if raw is None:
                return None
            return json.loads(raw)
        except Exception:
            logger.warning("redis_cache_get_failed", domain=domain)
            return None

    def set(
        self,
        domain: str,
        *,
        tier: str,
        confidence: str,
        mfa_score: float,
        evidence_hash: str,
        url_id: str,
    ) -> None:
        if not self.enabled:
            return
        payload = {
            "tier": tier,
            "confidence": confidence,
            "mfa_score": mfa_score,
            "evidence_hash": evidence_hash,
            "url_id": url_id,
        }
        try:
            self._get_client().setex(self._key(domain), _CACHE_TTL_SEC, json.dumps(payload))
        except Exception:
            logger.warning("redis_cache_set_failed", domain=domain)


def get_domain_cache() -> DomainTierCache:
    return DomainTierCache()


class RAGResponseCache:
    """Cache grounded RAG responses keyed by evidence_hash (MVP-3.7)."""

    def __init__(self, redis_url: str | None = None) -> None:
        self._redis_url = redis_url or os.getenv("REDIS_URL", "")
        self._client: Any | None = None

    @property
    def enabled(self) -> bool:
        return bool(self._redis_url)

    def _get_client(self) -> Any:
        if self._client is None:
            import redis

            self._client = redis.from_url(self._redis_url, decode_responses=True)
        return self._client

    def _key(self, evidence_hash: str) -> str:
        return f"rag:response:{evidence_hash}"

    def get(self, evidence_hash: str) -> dict[str, Any] | None:
        if not self.enabled or not evidence_hash:
            return None
        try:
            raw = self._get_client().get(self._key(evidence_hash))
            return json.loads(raw) if raw else None
        except Exception:
            logger.warning("rag_cache_get_failed")
            return None

    def set(self, evidence_hash: str, response: dict[str, Any]) -> None:
        if not self.enabled or not evidence_hash:
            return
        try:
            self._get_client().setex(
                self._key(evidence_hash),
                _CACHE_TTL_SEC,
                json.dumps(response),
            )
        except Exception:
            logger.warning("rag_cache_set_failed")


def get_rag_cache() -> RAGResponseCache:
    return RAGResponseCache()
