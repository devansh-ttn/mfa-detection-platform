import uuid
from dataclasses import dataclass

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mfa.core.errors import MFAError
from mfa.db.models import CrawlJob, Url
from mfa.ingestion.normalizer import NormalizedUrl, build_idempotency_key, normalize_url
from mfa.ingestion.queue import CrawlJobMessage, QueueBackend, get_queue

logger = structlog.get_logger(__name__)


@dataclass
class IngestedJob:
    job_id: uuid.UUID
    url_id: uuid.UUID
    normalized_url: str
    status: str
    idempotency_key: str
    duplicate: bool


@dataclass
class IngestionResult:
    jobs: list[IngestedJob]
    accepted: int
    duplicate: int
    invalid: list[str]


class IngestionService:
    def __init__(self, queue: QueueBackend | None = None) -> None:
        self._queue = queue or get_queue()

    async def ingest_urls(
        self,
        session: AsyncSession,
        *,
        urls: list[str],
        source_batch_id: str | None = None,
        priority: int = 0,
    ) -> IngestionResult:
        jobs: list[IngestedJob] = []
        duplicate_count = 0
        invalid: list[str] = []

        for raw_url in urls:
            try:
                normalized = normalize_url(raw_url)
            except ValueError as exc:
                invalid.append(f"{raw_url}: {exc}")
                continue

            job = await self._upsert_job(
                session,
                normalized=normalized,
                source_batch_id=source_batch_id,
                priority=priority,
            )
            if job.duplicate:
                duplicate_count += 1
            else:
                await self._queue.enqueue_crawl(
                    CrawlJobMessage(
                        job_id=job.job_id,
                        url_id=job.url_id,
                        normalized_url=job.normalized_url,
                        priority=priority,
                    )
                )
            jobs.append(job)

        await session.flush()

        logger.info(
            "ingestion_complete",
            accepted=len(jobs) - duplicate_count,
            duplicate=duplicate_count,
            invalid=len(invalid),
            source_batch_id=source_batch_id,
        )

        return IngestionResult(
            jobs=jobs,
            accepted=len(jobs) - duplicate_count,
            duplicate=duplicate_count,
            invalid=invalid,
        )

    async def _upsert_job(
        self,
        session: AsyncSession,
        *,
        normalized: NormalizedUrl,
        source_batch_id: str | None,
        priority: int,
    ) -> IngestedJob:
        idempotency_key = build_idempotency_key(normalized.url_hash, source_batch_id)

        existing_job = await session.scalar(
            select(CrawlJob).where(CrawlJob.idempotency_key == idempotency_key)
        )
        if existing_job is not None:
            url = await session.get(Url, existing_job.url_id)
            if url is None:
                raise MFAError(
                    "URL record missing for existing job",
                    code="data_integrity_error",
                    status_code=500,
                )
            return IngestedJob(
                job_id=existing_job.id,
                url_id=existing_job.url_id,
                normalized_url=url.normalized_url,
                status=existing_job.status,
                idempotency_key=idempotency_key,
                duplicate=True,
            )

        url = await session.scalar(select(Url).where(Url.url_hash == normalized.url_hash))
        if url is None:
            url = Url(
                url=normalized.original,
                normalized_url=normalized.normalized,
                url_hash=normalized.url_hash,
                domain=normalized.domain,
            )
            session.add(url)
            await session.flush()

        job = CrawlJob(
            url_id=url.id,
            status="queued",
            priority=priority,
            source_batch_id=source_batch_id,
            idempotency_key=idempotency_key,
        )
        session.add(job)
        await session.flush()

        return IngestedJob(
            job_id=job.id,
            url_id=url.id,
            normalized_url=url.normalized_url,
            status=job.status,
            idempotency_key=idempotency_key,
            duplicate=False,
        )
