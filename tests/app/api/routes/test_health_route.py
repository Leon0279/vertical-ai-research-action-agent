"""Operational health route tests."""

from dishka import make_async_container
from dishka.integrations.fastapi import FastapiProvider
from fastapi.testclient import TestClient

from app.api.app import create_app
from app.domain.models.health import ReadinessResult
from app.services.health import ReadinessService


class _FakeReadinessService:
    def __init__(self, result: ReadinessResult) -> None:
        self._result = result

    async def check(self) -> ReadinessResult:
        return self._result


def _client(readiness_service: _FakeReadinessService | None = None) -> TestClient:
    context = {}
    if readiness_service is not None:
        context[ReadinessService] = readiness_service
    container = make_async_container(FastapiProvider(), context=context)
    return TestClient(create_app(container))


def test_healthz_returns_process_liveness() -> None:
    with _client() as client:
        response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readyz_returns_safe_success_payload() -> None:
    with _client(
        _FakeReadinessService(
            ReadinessResult(
                status="ready",
                checks={
                    "redis": "ok",
                    "postgres": "ok",
                    "memory_schema": "ok",
                    "pgvector": "ok",
                },
            )
        )
    ) as client:
        response = client.get("/readyz")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "checks": {
            "redis": "ok",
            "postgres": "ok",
            "memory_schema": "ok",
            "pgvector": "ok",
        },
    }


def test_readyz_returns_503_without_internal_error_details() -> None:
    with _client(
        _FakeReadinessService(
            ReadinessResult(
                status="not_ready",
                checks={
                    "redis": "error",
                    "postgres": "ok",
                    "memory_schema": "ok",
                    "pgvector": "ok",
                },
            )
        )
    ) as client:
        response = client.get("/readyz")

    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"
    assert response.json()["checks"]["redis"] == "error"
    assert "dsn" not in response.text.lower()
    assert "password" not in response.text.lower()
