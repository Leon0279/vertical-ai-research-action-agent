"""Shared transport helpers for Memory query routes."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import Query, status
from pydantic import BeforeValidator
from starlette.responses import JSONResponse

from app.api.schemas.memory_query_error_response import MemoryQueryErrorResponse

_MEMORY_QUERY_ERROR_STATUS = {
    "INVALID_MEMORY_QUERY": status.HTTP_422_UNPROCESSABLE_CONTENT,
    "PROJECT_NOT_FOUND": status.HTTP_404_NOT_FOUND,
    "MEMORY_STORE_UNAVAILABLE": status.HTTP_503_SERVICE_UNAVAILABLE,
    "MEMORY_QUERY_FAILED": status.HTTP_500_INTERNAL_SERVER_ERROR,
}


def _parse_strict_decimal_integer(value: Any) -> Any:
    if isinstance(value, str) and value.isascii() and value.isdecimal():
        return int(value)
    return value


RequiredMemoryIdentifierQuery = Annotated[
    str,
    Query(min_length=1, max_length=200, pattern=r".*\S.*"),
]
MemoryLimitQuery = Annotated[
    int,
    Query(ge=1, le=100, strict=True),
    BeforeValidator(_parse_strict_decimal_integer),
]
MemoryCursorQuery = Annotated[
    str | None,
    Query(min_length=1, max_length=4096, pattern=r".*\S.*"),
]


def memory_query_error_response(
    *,
    error_code: str,
    error_reason: str,
    fallback_reason: str,
) -> JSONResponse:
    """Build a stable Memory API error and normalize unknown internal codes."""

    status_code = _MEMORY_QUERY_ERROR_STATUS.get(error_code)
    if status_code is None:
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        error_code = "MEMORY_QUERY_FAILED"
        error_reason = fallback_reason
    payload = MemoryQueryErrorResponse(
        error_code=error_code,
        error_reason=error_reason,
    )
    return JSONResponse(
        status_code=status_code,
        content=payload.model_dump(mode="json"),
    )
