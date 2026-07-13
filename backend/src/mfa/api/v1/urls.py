import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from mfa.core.errors import MFAError, NotFoundError
from mfa.db.models import CrawlJob, Url
from mfa.db.session import get_db_session
from mfa.ingestion.service import IngestionService
from mfa.schemas.errors import COMMON_ERROR_RESPONSES
from mfa.schemas.urls import (
    IngestedJobResponse,
    JobResponse,
    UrlSubmitRequest,
    UrlSubmitResponse,
)

router = APIRouter(tags=["ingestion"])


def get_ingestion_service() -> IngestionService:
    return IngestionService()


@router.post(
    "/urls",
    response_model=UrlSubmitResponse,
    status_code=202,
    responses=COMMON_ERROR_RESPONSES,
)
async def submit_urls(
    body: UrlSubmitRequest,
    session: AsyncSession = Depends(get_db_session),
    ingestion: IngestionService = Depends(get_ingestion_service),
) -> UrlSubmitResponse:
    if not body.urls:
        raise MFAError("At least one non-empty URL is required", code="validation_error")

    result = await ingestion.ingest_urls(
        session,
        urls=body.urls,
        source_batch_id=body.source_batch_id,
        priority=body.priority,
    )

    return UrlSubmitResponse(
        jobs=[
            IngestedJobResponse(
                job_id=job.job_id,
                url_id=job.url_id,
                normalized_url=job.normalized_url,
                status=job.status,
                idempotency_key=job.idempotency_key,
                duplicate=job.duplicate,
            )
            for job in result.jobs
        ],
        accepted=result.accepted,
        duplicate=result.duplicate,
        invalid=result.invalid,
    )


@router.get(
    "/jobs",
    response_model=list[JobResponse],
    responses=COMMON_ERROR_RESPONSES,
)
async def list_jobs(
    session: AsyncSession = Depends(get_db_session),
    status: str | None = Query(default=None, description="Filter by job status"),
    domain: str | None = Query(default=None, description="Filter by URL domain"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[JobResponse]:
    stmt = select(CrawlJob).options(joinedload(CrawlJob.url)).join(Url, CrawlJob.url_id == Url.id)

    if status is not None:
        stmt = stmt.where(CrawlJob.status == status)
    if domain is not None:
        stmt = stmt.where(Url.domain == domain)

    jobs = await session.scalars(
        stmt.order_by(CrawlJob.created_at.desc()).limit(limit).offset(offset)
    )

    result: list[JobResponse] = []
    for job in jobs:
        if job.url is None:
            continue
        result.append(
            JobResponse(
                job_id=job.id,
                url_id=job.url_id,
                status=job.status,
                url=job.url.url,
                normalized_url=job.url.normalized_url,
                domain=job.url.domain,
                priority=job.priority,
                source_batch_id=job.source_batch_id,
                error_message=job.error_message,
                created_at=job.created_at,
                updated_at=job.updated_at,
            )
        )
    return result


@router.get(
    "/jobs/{job_id}",
    response_model=JobResponse,
    responses=COMMON_ERROR_RESPONSES,
)
async def get_job(
    job_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> JobResponse:
    job = await session.scalar(
        select(CrawlJob).options(joinedload(CrawlJob.url)).where(CrawlJob.id == job_id)
    )
    if job is None or job.url is None:
        raise NotFoundError(f"Job not found: {job_id}", code="job_not_found")

    return JobResponse(
        job_id=job.id,
        url_id=job.url_id,
        status=job.status,
        url=job.url.url,
        normalized_url=job.url.normalized_url,
        domain=job.url.domain,
        priority=job.priority,
        source_batch_id=job.source_batch_id,
        error_message=job.error_message,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )
