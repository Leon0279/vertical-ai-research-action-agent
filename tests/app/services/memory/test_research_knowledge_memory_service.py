"""Tests for the Research Knowledge Memory browsing service."""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from app.common.utils.memory_cursor import decode_memory_cursor, encode_memory_cursor
from app.domain.models import ResearchKnowledgeUnitRecord
from app.domain.models.memory.memory_page_cursor import MemoryPageCursor
from app.services.memory.research_knowledge_memory_service import (
    ResearchKnowledgeMemoryService,
)
from app.services.memory.research_knowledge_memory_service_error import (
    ResearchKnowledgeMemoryServiceError,
)


class _Store:
    def __init__(self, *, records=None, error: Exception | None = None) -> None:
        self.records = records or []
        self.error = error
        self.calls: list[dict[str, object]] = []

    async def list_knowledge_units_page(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.records


def _record(knowledge_id: str, *, updated_at: datetime | None):
    return ResearchKnowledgeUnitRecord(
        knowledge_id=knowledge_id,
        owner_user_id="user-1",
        project_scope_id="project-1",
        visibility_scope="project",
        visibility_scope_effective="project",
        title=f"Title {knowledge_id}",
        summary=f"Summary {knowledge_id}",
        knowledge_type="concept",
        status="active",
        updated_at=updated_at,
    )


def test_defaults_to_project_scope_and_requests_limit_plus_one() -> None:
    store = _Store()

    page = asyncio.run(
        ResearchKnowledgeMemoryService(store).list_knowledge_units(
            user_id=" user-1 ",
            project_id=" project-1 ",
        )
    )

    assert page.project_id == "project-1"
    assert page.items == []
    assert store.calls == [
        {
            "owner_user_id": "user-1",
            "project_scope_id": "project-1",
            "visibility_scopes": ["project"],
            "limit": 21,
            "after_updated_at": None,
            "after_knowledge_id": None,
        }
    ]


def test_normalizes_scope_set_and_builds_scope_bound_cursor() -> None:
    newest = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)
    records = [
        _record("knowledge-3", updated_at=newest),
        _record("knowledge-2", updated_at=newest - timedelta(minutes=1)),
        _record("knowledge-1", updated_at=newest - timedelta(minutes=2)),
    ]
    store = _Store(records=records)

    page = asyncio.run(
        ResearchKnowledgeMemoryService(store).list_knowledge_units(
            user_id="user-1",
            project_id="project-1",
            visibility_scopes=["global", "project", "user", "project"],
            limit=2,
        )
    )

    assert [item.knowledge_id for item in page.items] == [
        "knowledge-3",
        "knowledge-2",
    ]
    assert store.calls[0]["visibility_scopes"] == ["user", "project", "global"]
    cursor = decode_memory_cursor(
        page.next_cursor or "",
        expected_collection="research_knowledge",
    )
    assert cursor.record_id == "knowledge-2"
    assert cursor.visibility_scopes == ["user", "project", "global"]


def test_scope_order_can_change_between_pages_but_scope_set_cannot() -> None:
    updated_at = datetime(2026, 9, 19, 11, 0, tzinfo=UTC)
    cursor = encode_memory_cursor(
        MemoryPageCursor(
            collection="research_knowledge",
            updated_at=updated_at,
            record_id="knowledge-7",
            visibility_scopes=["user", "project"],
        )
    )
    store = _Store()
    service = ResearchKnowledgeMemoryService(store)

    asyncio.run(
        service.list_knowledge_units(
            user_id="user-1",
            project_id="project-1",
            visibility_scopes=["project", "user"],
            cursor=cursor,
        )
    )
    assert store.calls[0]["after_updated_at"] == updated_at
    assert store.calls[0]["after_knowledge_id"] == "knowledge-7"

    with pytest.raises(ResearchKnowledgeMemoryServiceError) as caught:
        asyncio.run(
            service.list_knowledge_units(
                user_id="user-1",
                project_id="project-1",
                visibility_scopes=["project"],
                cursor=cursor,
            )
        )
    assert caught.value.error_code == "INVALID_MEMORY_QUERY"


@pytest.mark.parametrize("scopes", [[], ["unknown"], ["project,user"], [""]])
def test_rejects_invalid_visibility_scopes(scopes) -> None:
    with pytest.raises(ResearchKnowledgeMemoryServiceError) as caught:
        asyncio.run(
            ResearchKnowledgeMemoryService(_Store()).list_knowledge_units(
                user_id="user-1",
                project_id="project-1",
                visibility_scopes=scopes,
            )
        )
    assert caught.value.error_code == "INVALID_MEMORY_QUERY"


def test_rejects_cross_collection_cursor_and_wraps_store_failure() -> None:
    cursor = encode_memory_cursor(
        MemoryPageCursor(
            collection="policies",
            updated_at=datetime(2026, 9, 19, 11, 0, tzinfo=UTC),
            record_id="policy-1",
        )
    )
    with pytest.raises(ResearchKnowledgeMemoryServiceError) as caught:
        asyncio.run(
            ResearchKnowledgeMemoryService(_Store()).list_knowledge_units(
                user_id="user-1",
                project_id="project-1",
                cursor=cursor,
            )
        )
    assert caught.value.error_code == "INVALID_MEMORY_QUERY"

    with pytest.raises(ResearchKnowledgeMemoryServiceError) as caught:
        asyncio.run(
            ResearchKnowledgeMemoryService(
                _Store(error=RuntimeError("password=secret"))
            ).list_knowledge_units(user_id="user-1", project_id="project-1")
        )
    assert caught.value.error_code == "MEMORY_STORE_UNAVAILABLE"
    assert "secret" not in caught.value.error_reason


def test_rejects_missing_updated_at_when_next_page_is_needed() -> None:
    records = [
        _record("knowledge-2", updated_at=None),
        _record("knowledge-1", updated_at=None),
    ]
    with pytest.raises(ResearchKnowledgeMemoryServiceError) as caught:
        asyncio.run(
            ResearchKnowledgeMemoryService(_Store(records=records)).list_knowledge_units(
                user_id="user-1",
                project_id="project-1",
                limit=1,
            )
        )
    assert caught.value.error_code == "MEMORY_QUERY_FAILED"
