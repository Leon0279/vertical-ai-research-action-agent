"""Route contract tests for API boundary."""

import pytest
from fastapi.testclient import TestClient

from app.api.app import app
from app.api.routes.agent import router


_client = TestClient(app)


def test_run_route_exists() -> None:
    matches = [route for route in router.routes if route.path == "/v1/agent/run"]
    assert len(matches) == 1
    methods = matches[0].methods or set()
    assert "POST" in methods


def test_run_request_openapi_describes_iteration_budget() -> None:
    request_schema = app.openapi()["components"]["schemas"]["AgentRunRequest"]
    iteration_budget_schema = request_schema["properties"]["iteration_budget"]

    assert iteration_budget_schema["type"] == "integer"
    assert iteration_budget_schema["default"] == 2
    assert iteration_budget_schema["minimum"] == 1
    assert iteration_budget_schema["maximum"] == 5


@pytest.mark.parametrize(
    "iteration_budget",
    [0, -1, 6, 1.5, "2", None],
)
def test_run_route_rejects_invalid_iteration_budget(
    iteration_budget: object,
) -> None:
    response = _client.post(
        "/v1/agent/run",
        json={
            "query": "Explain retrieval strategies.",
            "user_id": "user-1",
            "iteration_budget": iteration_budget,
        },
    )

    assert response.status_code == 422
