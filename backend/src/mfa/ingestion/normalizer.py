import hashlib
from dataclasses import dataclass
from urllib.parse import urlparse, urlunparse


@dataclass(frozen=True)
class NormalizedUrl:
    original: str
    normalized: str
    url_hash: str
    domain: str


def normalize_url(raw_url: str) -> NormalizedUrl:
    stripped = raw_url.strip()
    if not stripped:
        raise ValueError("URL must not be empty")

    parsed = urlparse(stripped if "://" in stripped else f"https://{stripped}")
    if not parsed.netloc:
        raise ValueError(f"Invalid URL: {raw_url}")

    scheme = (parsed.scheme or "https").lower()
    host = parsed.hostname.lower() if parsed.hostname else ""
    port = parsed.port
    default_port = 443 if scheme == "https" else 80
    netloc = host if port is None or port == default_port else f"{host}:{port}"

    path = parsed.path or "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")

    normalized = urlunparse((scheme, netloc, path, "", parsed.query, ""))
    url_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    return NormalizedUrl(
        original=stripped,
        normalized=normalized,
        url_hash=url_hash,
        domain=host,
    )


def build_idempotency_key(url_hash: str, source_batch_id: str | None) -> str:
    batch = source_batch_id or "default"
    return hashlib.sha256(f"{url_hash}:{batch}".encode()).hexdigest()
