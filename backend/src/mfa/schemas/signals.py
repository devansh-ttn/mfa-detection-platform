"""Pydantic models for signal_snapshots JSONB payloads and API responses."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# TODO(MVP): Bump version and extend SignalFeatures when enrichment + dual-persona
# signals ship — see docs/SIGNALS.md and docs/ROADMAP.md.
SIGNAL_SCHEMA_VERSION = "v1"
SUPPORTED_SCHEMA_VERSIONS: frozenset[str] = frozenset({SIGNAL_SCHEMA_VERSION, "poc-v1"})

Persona = Literal["direct", "referral"]

CRAWL_FEATURE_NAMES: tuple[str, ...] = (
    "ad_to_content_ratio",
    "ads_above_fold",
    "ad_slots_count",
    "sticky_ad_count",
    "content_word_count",
    "refresh_events_60s",
    "avg_refresh_interval_sec",
    "content_uniqueness_score",
    "author_page_exists",
    "slideshow_pagination_depth",
    "video_autoplay_count",
    "page_load_ad_latency_ms",
    "iframe_ad_count",
    "native_ad_count",
    "outbound_link_count",
    "image_to_text_ratio",
)

# TODO(MVP): Merge into SignalFeatures when enrichment workers are wired.
ENRICHMENT_FEATURE_NAMES: tuple[str, ...] = (
    "domain_age_days",
    "paid_traffic_pct",
    "social_traffic_pct",
    "organic_traffic_pct",
    "referral_direct_delta_score",
    "sellers_json_risk_tier",
    "historical_spend_usd",
    "campaign_ctr_vs_benchmark",
    "simhash_dup_rate",
    "llm_content_quality_score",
)


class SignalFeatures(BaseModel):
    """DOM and content-heuristic features extracted by the crawl pipeline."""

    model_config = ConfigDict(extra="forbid")

    ad_to_content_ratio: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Ratio of ad area to content area (0–1)"
    )
    ads_above_fold: int | None = Field(default=None, ge=0)
    ad_slots_count: int | None = Field(default=None, ge=0)
    sticky_ad_count: int | None = Field(default=None, ge=0)
    content_word_count: int | None = Field(default=None, ge=0)
    refresh_events_60s: int | None = Field(
        default=None,
        ge=0,
        description="Refresh count during dwell; null when dwell not measured",
    )
    avg_refresh_interval_sec: float | None = Field(default=None, ge=0.0)
    content_uniqueness_score: float | None = Field(default=None, ge=0.0, le=1.0)
    author_page_exists: bool | None = None
    slideshow_pagination_depth: int | None = Field(default=None, ge=0)
    video_autoplay_count: int | None = Field(default=None, ge=0)
    page_load_ad_latency_ms: float | None = Field(default=None, ge=0.0)
    iframe_ad_count: int | None = Field(default=None, ge=0)
    native_ad_count: int | None = Field(default=None, ge=0)
    outbound_link_count: int | None = Field(default=None, ge=0)
    image_to_text_ratio: float | None = Field(default=None, ge=0.0)


class SignalSnapshotPayload(BaseModel):
    """Canonical JSONB document stored in signal_snapshots.signals."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = SIGNAL_SCHEMA_VERSION
    crawl_ts: datetime
    features: SignalFeatures

    @field_validator("schema_version")
    @classmethod
    def supported_schema_version(cls, value: str) -> str:
        if value not in SUPPORTED_SCHEMA_VERSIONS:
            raise ValueError(f"unsupported schema_version: {value}")
        return value

    def to_db(self) -> dict[str, Any]:
        data = self.model_dump(mode="json")
        features = data.pop("features")
        data["schema_version"] = SIGNAL_SCHEMA_VERSION
        data.update(features)
        return data

    @classmethod
    def from_db(cls, data: dict[str, Any]) -> SignalSnapshotPayload:
        raw_version = data.get("schema_version", SIGNAL_SCHEMA_VERSION)
        if raw_version == "poc-v1":
            raw_version = SIGNAL_SCHEMA_VERSION
        known = set(CRAWL_FEATURE_NAMES)
        features = {key: data[key] for key in known if key in data}
        return cls(
            schema_version=raw_version,
            crawl_ts=data["crawl_ts"],
            features=SignalFeatures.model_validate(features),
        )


class SignalSnapshotResponse(BaseModel):
    """API representation of a signal_snapshots row."""

    snapshot_id: uuid.UUID
    url_id: uuid.UUID
    version: int
    signals: dict[str, Any]
    evidence_hash: str
    persona: Persona
    crawl_duration_sec: float | None
    created_at: datetime

    @model_validator(mode="after")
    def validate_signals_payload(self) -> SignalSnapshotResponse:
        if not _EVIDENCE_HASH_RE.fullmatch(self.evidence_hash):
            raise ValueError("invalid evidence_hash format")
        SignalSnapshotPayload.from_db(self.signals)
        return self


class SignalSnapshotListResponse(BaseModel):
    url_id: uuid.UUID
    snapshots: list[SignalSnapshotResponse]
    total: int
    limit: int
    offset: int


_EVIDENCE_HASH_RE = re.compile(r"^[a-f0-9]{64}$")


def compute_evidence_hash(signals: dict[str, Any]) -> str:
    """SHA-256 of canonical JSON for audit binding."""
    canonical = json.dumps(signals, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
