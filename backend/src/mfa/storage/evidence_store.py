"""Evidence artifact storage — local filesystem (POC) or S3 (MVP)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Protocol


class EvidenceStore(Protocol):
    def write_bytes(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str: ...
    def get_signed_url(self, key: str, expires_sec: int = 3600) -> str: ...


class LocalEvidenceStore:
    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = base_dir or Path(os.getenv("EVIDENCE_DIR", "backend/evidence"))

    def write_bytes(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        path = self.base_dir / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return str(path)

    def get_signed_url(self, key: str, expires_sec: int = 3600) -> str:
        return f"/api/v1/evidence/{key}"


class S3EvidenceStore:
    def __init__(self) -> None:
        import boto3

        endpoint = os.getenv("AWS_ENDPOINT_URL") or None
        self.bucket = os.getenv("S3_EVIDENCE_BUCKET", "mfa-dev-evidence")
        self._client = boto3.client("s3", endpoint_url=endpoint, region_name=os.getenv("AWS_DEFAULT_REGION", "us-east-1"))

    def write_bytes(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        self._client.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=content_type)
        return f"s3://{self.bucket}/{key}"

    def get_signed_url(self, key: str, expires_sec: int = 3600) -> str:
        return self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=expires_sec,
        )


def get_evidence_store() -> EvidenceStore:
    if os.getenv("S3_EVIDENCE_BUCKET"):
        return S3EvidenceStore()
    return LocalEvidenceStore()
