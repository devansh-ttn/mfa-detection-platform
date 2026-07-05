import pytest

from mfa.ingestion.normalizer import build_idempotency_key, normalize_url


def test_normalize_url_strips_trailing_slash() -> None:
    result = normalize_url("https://Example.com/path/")
    assert result.normalized == "https://example.com/path"
    assert result.domain == "example.com"


def test_normalize_url_adds_scheme() -> None:
    result = normalize_url("www.example.com/article")
    assert result.normalized == "https://www.example.com/article"


def test_normalize_url_rejects_empty() -> None:
    with pytest.raises(ValueError, match="empty"):
        normalize_url("   ")


def test_idempotency_key_stable() -> None:
    url_hash = normalize_url("https://example.com").url_hash
    key_a = build_idempotency_key(url_hash, "batch-1")
    key_b = build_idempotency_key(url_hash, "batch-1")
    key_c = build_idempotency_key(url_hash, "batch-2")
    assert key_a == key_b
    assert key_a != key_c
