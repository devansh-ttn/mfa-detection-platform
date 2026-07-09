import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Url(Base):
    __tablename__ = "urls"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_url: Mapped[str] = mapped_column(Text, nullable=False)
    url_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    domain: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    crawl_jobs: Mapped[list["CrawlJob"]] = relationship(back_populates="url")
    signal_snapshots: Mapped[list["SignalSnapshot"]] = relationship(back_populates="url")
    score_jobs: Mapped[list["ScoreJob"]] = relationship(back_populates="url")
    classifications: Mapped[list["Classification"]] = relationship(back_populates="url")


class CrawlJob(Base):
    __tablename__ = "crawl_jobs"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_crawl_jobs_idempotency_key"),
        Index("ix_crawl_jobs_status_priority", "status", "priority"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    url_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("urls.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued", index=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    source_batch_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Populated on failure; drives skip-logic in claim_next_crawl_job.
    # Values: "transient" | "not_found" | "http_error" | "timeout" | "robots_denied" | "invalid_url"
    crawl_error_type: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    url: Mapped["Url"] = relationship(back_populates="crawl_jobs")


class SignalSnapshot(Base):
    __tablename__ = "signal_snapshots"
    __table_args__ = (
        UniqueConstraint("url_id", "version", name="uq_signal_snapshots_url_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    url_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("urls.id"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    signals: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    evidence_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    persona: Mapped[str] = mapped_column(String(32), nullable=False, default="direct")
    crawl_duration_sec: Mapped[float | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    url: Mapped["Url"] = relationship(back_populates="signal_snapshots")
    score_jobs: Mapped[list["ScoreJob"]] = relationship(back_populates="signal_snapshot")


class ScoreJob(Base):
    __tablename__ = "score_jobs"
    __table_args__ = (
        UniqueConstraint("signal_snapshot_id", name="uq_score_jobs_signal_snapshot_id"),
        Index("ix_score_jobs_status_priority_created", "status", "priority", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    url_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("urls.id"), nullable=False
    )
    signal_snapshot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("signal_snapshots.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued", index=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    url: Mapped["Url"] = relationship(back_populates="score_jobs")
    signal_snapshot: Mapped["SignalSnapshot"] = relationship(back_populates="score_jobs")


class Classification(Base):
    __tablename__ = "classifications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    url_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("urls.id"), nullable=False, index=True
    )
    signal_snapshot_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("signal_snapshots.id"), nullable=True
    )
    tier: Mapped[str] = mapped_column(String(32), nullable=False)
    mfa_score: Mapped[float] = mapped_column(nullable=False)
    confidence: Mapped[str] = mapped_column(String(16), nullable=False)
    top_signals: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    explanation: Mapped[str] = mapped_column(Text, nullable=False, default="")
    evidence_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    classifier: Mapped[str] = mapped_column(String(32), nullable=False, default="xgboost")
    schema_version: Mapped[str] = mapped_column(String(8), nullable=False, default="v1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    url: Mapped["Url"] = relationship(back_populates="classifications")


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(128), nullable=False, default="system")
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    evidence_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
