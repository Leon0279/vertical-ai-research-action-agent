"""Route contract tests for API boundary."""

from app.api.routes.agent import router


def test_run_route_exists() -> None:
    matches = [route for route in router.routes if route.path == "/v1/agent/run"]
    assert len(matches) == 1
    methods = matches[0].methods or set()
    assert "POST" in methods

