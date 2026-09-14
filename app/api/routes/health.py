"""Operational health route definitions."""

from fastapi import APIRouter, status
from starlette.responses import JSONResponse

from app.api.schemas.health_response import HealthResponse
from app.api.schemas.readiness_response import ReadinessResponse
from app.services.health import ReadinessService

router = APIRouter(tags=["health"])
_readiness_service = ReadinessService()


@router.get("/healthz", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Return process liveness without touching external services."""

    return HealthResponse(status="ok")


@router.get(
    "/readyz",
    response_model=ReadinessResponse,
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "model": ReadinessResponse,
            "description": "One or more required local state stores are unavailable.",
        }
    },
)
async def readiness() -> ReadinessResponse | JSONResponse:
    """Return dependency readiness without exposing connection details."""

    result = await _readiness_service.check()
    response = ReadinessResponse(status=result.status, checks=result.checks)
    if result.status == "not_ready":
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=response.model_dump(),
        )
    return response
