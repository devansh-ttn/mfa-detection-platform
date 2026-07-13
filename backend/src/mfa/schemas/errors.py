"""Structured API error models and OpenAPI response definitions."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

ERROR_EXAMPLE = {
    "error": "URL not found: 550e8400-e29b-41d4-a716-446655440000",
    "code": "url_not_found",
    "details": {},
}


class ErrorResponse(BaseModel):
    """Standard error envelope for all v1 endpoints."""

    model_config = ConfigDict(json_schema_extra={"examples": [ERROR_EXAMPLE]})

    error: str = Field(..., description="Human-readable error message")
    code: str = Field(..., description="Machine-readable error code")
    details: dict[str, Any] = Field(default_factory=dict, description="Optional context")


COMMON_ERROR_RESPONSES: dict[int, dict[str, Any]] = {
    400: {
        "model": ErrorResponse,
        "description": "Validation or business rule error",
        "content": {
            "application/json": {
                "examples": {
                    "validation_error": {
                        "summary": "Invalid request body",
                        "value": {
                            "error": "At least one non-empty URL is required",
                            "code": "validation_error",
                            "details": {},
                        },
                    }
                }
            }
        },
    },
    404: {
        "model": ErrorResponse,
        "description": "Resource not found",
        "content": {
            "application/json": {
                "examples": {
                    "url_not_found": {
                        "summary": "URL not found",
                        "value": ERROR_EXAMPLE,
                    },
                    "job_not_found": {
                        "summary": "Crawl job not found",
                        "value": {
                            "error": "Job not found: 550e8400-e29b-41d4-a716-446655440000",
                            "code": "job_not_found",
                            "details": {},
                        },
                    },
                    "classification_not_found": {
                        "summary": "No classification for URL",
                        "value": {
                            "error": "No classification found for URL: 550e8400-e29b-41d4-a716-446655440000",
                            "code": "classification_not_found",
                            "details": {},
                        },
                    },
                }
            }
        },
    },
    422: {
        "description": "Request validation failed (FastAPI/Pydantic)",
    },
}
