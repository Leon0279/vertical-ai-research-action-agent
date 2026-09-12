"""Schema tests for project query responses."""

from datetime import UTC, datetime

from app.api.schemas import ListProjectIdsResponse, ProjectDetailsResponse


def test_list_project_ids_response_defaults_to_empty_list() -> None:
    response = ListProjectIdsResponse()

    assert response.model_dump(mode="json") == {"project_ids": []}


def test_project_details_response_serializes_profile_timestamps() -> None:
    response = ProjectDetailsResponse(
        project_id="project-1",
        project_name="Agent MVP",
        project_description="Build it.",
        constraints=["Keep APIs stable"],
        profile_created_at=datetime(2026, 9, 1, 8, 0, tzinfo=UTC),
        profile_updated_at=datetime(2026, 9, 2, 9, 30, tzinfo=UTC),
    )

    dumped = response.model_dump(mode="json")

    assert dumped["project_id"] == "project-1"
    assert dumped["profile_created_at"] == "2026-09-01T08:00:00Z"
    assert dumped["profile_updated_at"] == "2026-09-02T09:30:00Z"
    assert "project_profile_id" not in dumped
