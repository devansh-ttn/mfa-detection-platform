from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse


class MFAError(Exception):
    def __init__(
        self,
        message: str,
        code: str,
        status_code: int = 400,
        details: dict[str, Any] | None = None,
    ):
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


class NotFoundError(MFAError):
    def __init__(
        self,
        message: str,
        code: str = "not_found",
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message=message, code=code, status_code=404, details=details)


def error_response(
    *,
    error: str,
    code: str,
    status_code: int,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": error, "code": code, "details": details or {}},
    )


async def mfa_error_handler(_request: Request, exc: MFAError) -> JSONResponse:
    return error_response(
        error=exc.message,
        code=exc.code,
        status_code=exc.status_code,
        details=exc.details,
    )
