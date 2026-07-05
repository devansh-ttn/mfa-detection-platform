import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from mfa.core.errors import MFAError, NotFoundError
from mfa.db.models import CrawlJob
from mfa.db.session import get_db_session
from mfa.ingestion.service import IngestionService
from mfa.schemas.urls import (
    IngestedJobResponse,
    JobResponse,
    UrlSubmitRequest,
    UrlSubmitResponse,
)

router = APIRouter(tags=["ingestion"])


def get_ingestion_service() -> IngestionService:
    return IngestionService()


@router.post("/urls", response_model=UrlSubmitResponse, status_code=202)
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


@router.get("/jobs/{job_id}", response_model=JobResponse)
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
