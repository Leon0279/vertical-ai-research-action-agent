"""Schema validation tests for project creation."""

import pytest
from pydantic import ValidationError

from app.api.schemas import CreateProjectRequest, CreateProjectResponse


def test_create_project_request_minimal() -> None:
    request = CreateProjectRequest(
        user_id=" user-1 ",
        project_name=" Agent MVP ",
        project_description=" Build the first version. ",
    )

    assert request.user_id == "user-1"
    assert request.project_name == "Agent MVP"
    assert request.project_description == "Build the first version."
    assert request.constraints == []


def test_create_project_request_accepts_optional_profile_fields() -> None:
    request = CreateProjectRequest(
        user_id="user-1",
        project_name="Agent MVP",
        project_description="Build the first version.",
        project_goal="Deliver an MVP.",
        domain="AI engineering",
        current_stage="implementation",
        constraints=[" small scope ", "typed boundaries"],
        important_context="Prefer minimal dependencies.",
    )

    assert request.constraints == ["small scope", "typed boundaries"]
    assert request.project_goal == "Deliver an MVP."


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("user_id", "   "),
        ("project_name", ""),
        ("project_description", "   "),
    ],
)
def test_create_project_request_rejects_blank_required_fields(
    field: str,
    value: str,
) -> None:
    payload = {
        "user_id": "user-1",
        "project_name": "Agent MVP",
        "project_description": "Build it.",
        field: value,
    }

    with pytest.raises(ValidationError):
        CreateProjectRequest(**payload)


def test_create_project_request_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        CreateProjectRequest(
            user_id="user-1",
            project_name="Agent MVP",
            project_description="Build it.",
            project_id="caller-controlled",
        )


def test_create_project_request_rejects_more_than_twenty_constraints() -> None:
    with pytest.raises(ValidationError):
        CreateProjectRequest(
            user_id="user-1",
            project_name="Agent MVP",
            project_description="Build it.",
            constraints=[f"constraint-{index}" for index in range(21)],
        )


def test_create_project_response_contains_only_project_id() -> None:
    response = CreateProjectResponse(project_id="project-1")

    assert response.model_dump(mode="json") == {"project_id": "project-1"}
