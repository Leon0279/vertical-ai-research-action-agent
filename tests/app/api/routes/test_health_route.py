"""Operational health route tests."""

from fastapi.testclient import TestClient

from app.api.app import app
from app.api.routes import health
from app.domain.models.health import ReadinessResult


class _FakeReadinessService:
    def __init__(self, result: ReadinessResult) -> None:
        self._result = result

    async def check(self) -> ReadinessResult:
        return self._result


_client = TestClient(app)


def test_healthz_returns_process_liveness() -> None:
    response = _client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readyz_returns_safe_success_payload(monkeypatch) -> None:
    monkeypatch.setattr(
        health,
        "_readiness_service",
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
        ),
    )

    response = _client.get("/readyz")

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


def test_readyz_returns_503_without_internal_error_details(monkeypatch) -> None:
    monkeypatch.setattr(
        health,
        "_readiness_service",
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
        ),
    )

    response = _client.get("/readyz")

    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"
    assert response.json()["checks"]["redis"] == "error"
    assert "dsn" not in response.text.lower()
    assert "password" not in response.text.lower()
