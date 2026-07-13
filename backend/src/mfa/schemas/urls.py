import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from mfa.schemas.openapi_examples import JOB_RESPONSE, URL_SUBMIT_REQUEST, URL_SUBMIT_RESPONSE


class UrlSubmitRequest(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [URL_SUBMIT_REQUEST]})

    urls: list[str] = Field(..., min_length=1, max_length=500)
    source_batch_id: str | None = Field(default=None, max_length=128)
    priority: int = Field(default=0, ge=0, le=100)

    @field_validator("urls")
    @classmethod
    def strip_urls(cls, urls: list[str]) -> list[str]:
        return [u.strip() for u in urls if u.strip()]


class IngestedJobResponse(BaseModel):
    job_id: uuid.UUID
    url_id: uuid.UUID
    normalized_url: str
    status: str
    idempotency_key: str
    duplicate: bool


class UrlSubmitResponse(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [URL_SUBMIT_RESPONSE]})

    jobs: list[IngestedJobResponse]
    accepted: int
    duplicate: int
    invalid: list[str]


class JobResponse(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [JOB_RESPONSE]})

    job_id: uuid.UUID
    url_id: uuid.UUID
    status: str
    url: str
    normalized_url: str
    domain: str
    priority: int
    source_batch_id: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime
