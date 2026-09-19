"""Tests for the independent Research Knowledge Memory list API."""

from datetime import UTC, datetime
from typing import Any

from dishka import make_async_container
from dishka.integrations.fastapi import FastapiProvider
from fastapi.testclient import TestClient
from httpx import Response

from app.api.app import create_app
from app.domain.models import ResearchKnowledgeUnitRecord, SourceReference
from app.domain.models.memory.research_knowledge_memory_page import (
    ResearchKnowledgeMemoryPage,
)
from app.services.use_cases.contracts.list_research_knowledge_memories_use_case_service_protocol import (
    ListResearchKnowledgeMemoriesUseCaseServiceProtocol,
)
from app.services.use_cases.list_research_knowledge_memories_use_case_error import (
    ListResearchKnowledgeMemoriesUseCaseError,
)


class _UseCase:
    def __init__(self, *, page=None, error: Exception | None = None) -> None:
        self.page = page or ResearchKnowledgeMemoryPage(project_id="project-1")
        self.error = error
        self.calls: list[dict[str, object]] = []

    async def execute(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.page


def _request(use_case: _UseCase, path: str, **kwargs: Any) -> Response:
    container = make_async_container(
        FastapiProvider(),
        context={ListResearchKnowledgeMemoriesUseCaseServiceProtocol: use_case},
    )
    with TestClient(create_app(container), raise_server_exceptions=False) as client:
        return client.get(path, **kwargs)


def _params(**overrides: object) -> dict[str, object]:
    return {"user_id": "user-1", "project_id": "project-1", **overrides}


def _record() -> ResearchKnowledgeUnitRecord:
    return ResearchKnowledgeUnitRecord(
        knowledge_id="knowledge-1",
        owner_user_id="private-user-id",
        project_scope_id="private-project-scope",
        visibility_scope="project",
        visibility_scope_effective="project",
        title="Reinforcement learning basics",
        summary="An agent improves behavior using reward feedback.",
        knowledge_type="concept",
        topic_tags=["reinforcement-learning"],
        confidence=0.91,
        source_refs=[
            SourceReference(
                source_type="paper",
                source_url="https://example.test/paper",
                title="RL paper",
            )
        ],
        source_type="paper",
        created_by="llm",
        status="active",
        created_at=datetime(2026, 9, 19, 8, 0, tzinfo=UTC),
        updated_at=datetime(2026, 9, 19, 9, 0, tzinfo=UTC),
        archived_at=datetime(2026, 9, 18, 9, 0, tzinfo=UTC),
        pruned_at=None,
        freshness_sensitivity="medium",
        freshness_status="aging",
        last_verified_at=datetime(2026, 9, 19, 7, 0, tzinfo=UTC),
        freshness_checked_at=datetime(2026, 9, 19, 7, 30, tzinfo=UTC),
        staleness_reason="Needs periodic verification.",
        dedupe_key="private-dedupe-key",
        canonical_knowledge_id="private-canonical-id",
        is_canonical=True,
        merged_into_id=None,
        embedding_text="private embedding text",
        embedding_vector=[0.1, 0.2],
        embedding_model="private-model",
        embedding_version="private-version",
        derived_from_session_id="session-1",
        derived_from_run_id="run-1",
    )


def test_route_returns_public_fields_and_repeated_scopes() -> None:
    use_case = _UseCase(
        page=ResearchKnowledgeMemoryPage(
            project_id="project-1",
            items=[_record()],
            next_cursor="next-page",
        )
    )
    response = _request(
        use_case,
        "/v1/memories/research-knowledge",
        params=[
            ("user_id", "user-1"),
            ("project_id", "project-1"),
            ("visibility_scope", "project"),
            ("visibility_scope", "user"),
            ("limit", "10"),
            ("cursor", "current-page"),
        ],
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["project_id"] == "project-1"
    assert payload["next_cursor"] == "next-page"
    assert payload["items"][0]["knowledge_id"] == "knowledge-1"
    assert payload["items"][0]["freshness_status"] == "aging"
    assert payload["items"][0]["source_refs"][0]["source_type"] == "paper"
    serialized = response.text
    assert "private-user-id" not in serialized
    assert "private-project-scope" not in serialized
    public_keys = set(payload["items"][0])
    assert public_keys.isdisjoint(
        {
            "owner_user_id",
            "project_scope_id",
            "status",
            "archived_at",
            "pruned_at",
            "dedupe_key",
            "canonical_knowledge_id",
            "is_canonical",
            "merged_into_id",
            "embedding_text",
            "embedding_vector",
            "embedding_model",
            "embedding_version",
        }
    )
    assert use_case.calls == [
        {
            "user_id": "user-1",
            "project_id": "project-1",
            "visibility_scopes": ["project", "user"],
            "limit": 10,
            "cursor": "current-page",
        }
    ]


def test_route_defaults_to_service_scope_and_returns_empty_page() -> None:
    use_case = _UseCase()
    response = _request(
        use_case,
        "/v1/memories/research-knowledge",
        params=_params(),
    )
    assert response.status_code == 200
    assert response.json() == {
        "project_id": "project-1",
        "items": [],
        "next_cursor": None,
    }
    assert use_case.calls[0]["visibility_scopes"] is None
    assert use_case.calls[0]["limit"] == 20


def test_route_rejects_invalid_visibility_scope_queries() -> None:
    cases = [
        _params(visibility_scope="unknown"),
        _params(visibility_scope=""),
        _params(visibility_scope="project,user"),
    ]
    for params in cases:
        response = _request(
            _UseCase(),
            "/v1/memories/research-knowledge",
            params=params,
        )
        assert response.status_code == 422
        assert response.json()["error_code"] == "INVALID_MEMORY_QUERY"


def test_route_maps_errors_and_hides_unexpected_details() -> None:
    for code, expected_status in [
        ("PROJECT_NOT_FOUND", 404),
        ("INVALID_MEMORY_QUERY", 422),
        ("MEMORY_STORE_UNAVAILABLE", 503),
        ("MEMORY_QUERY_FAILED", 500),
    ]:
        response = _request(
            _UseCase(
                error=ListResearchKnowledgeMemoriesUseCaseError(
                    error_code=code,
                    error_reason="安全错误说明。",
                )
            ),
            "/v1/memories/research-knowledge",
            params=_params(),
        )
        assert response.status_code == expected_status
        assert response.json()["error_code"] == code

    response = _request(
        _UseCase(error=RuntimeError("postgresql://user:secret@example.test/db")),
        "/v1/memories/research-knowledge",
        params=_params(),
    )
    assert response.status_code == 500
    assert "secret" not in response.text


def test_route_openapi_exposes_independent_repeated_enum_parameter() -> None:
    schema = _request(_UseCase(), "/openapi.json").json()
    operation = schema["paths"]["/v1/memories/research-knowledge"]["get"]

    assert operation["tags"] == ["research-knowledge-memory"]
    parameters = {item["name"]: item for item in operation["parameters"]}
    scope_schema = parameters["visibility_scope"]["schema"]
    assert parameters["user_id"]["required"] is True
    assert parameters["project_id"]["required"] is True
    assert scope_schema["anyOf"][0]["type"] == "array"
    enum_ref = scope_schema["anyOf"][0]["items"]
    assert set(enum_ref["enum"]) == {"user", "project", "domain", "global"}
    assert set(operation["responses"]) >= {"200", "404", "422", "500", "503"}
