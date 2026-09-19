"""Tests for the Action Memory application service."""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from app.common.utils.memory_cursor import decode_memory_cursor, encode_memory_cursor
from app.domain.models import ActionMemoryRecord, MemoryCollectionSummary
from app.domain.models.memory.memory_page_cursor import MemoryPageCursor
from app.services.memory.action_memory_service import ActionMemoryService
from app.services.memory.action_memory_service_error import ActionMemoryServiceError


class _ActionStore:
    def __init__(
        self,
        *,
        records: list[ActionMemoryRecord] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.records = records or []
        self.error = error
        self.calls: list[dict[str, object]] = []

    async def list_actions_page(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.records

    async def summarize_actions(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return MemoryCollectionSummary(count=3)


def _record(
    action_id: str,
    *,
    action_status: str = "todo",
    updated_at: datetime | None,
) -> ActionMemoryRecord:
    return ActionMemoryRecord(
        action_id=action_id,
        user_id="user-1",
        project_id="project-1",
        action_title=f"Action {action_id}",
        action_status=action_status,
        record_status=(
            "archived" if action_status in {"done", "cancelled"} else "active"
        ),
        updated_at=updated_at,
    )


def test_action_service_defaults_to_pending_statuses_and_limit_plus_one() -> None:
    store = _ActionStore()
    service = ActionMemoryService(store)

    page = asyncio.run(
        service.list_actions(
            user_id=" user-1 ",
            project_id=" project-1 ",
        )
    )

    assert page.project_id == "project-1"
    assert page.items == []
    assert page.next_cursor is None
    assert store.calls == [
        {
            "user_id": "user-1",
            "project_id": "project-1",
            "action_statuses": ["todo", "in_progress", "blocked"],
            "limit": 21,
            "after_updated_at": None,
            "after_action_id": None,
        }
    ]


def test_action_service_deduplicates_and_canonicalizes_statuses() -> None:
    store = _ActionStore()
    service = ActionMemoryService(store)

    asyncio.run(
        service.list_actions(
            user_id="user-1",
            project_id="project-1",
            action_statuses=["done", "in_progress", "done"],
        )
    )

    assert store.calls[0]["action_statuses"] == ["in_progress", "done"]


def test_action_service_builds_filter_bound_next_cursor() -> None:
    newest = datetime(2026, 9, 18, 12, 0, tzinfo=UTC)
    records = [
        _record("action-3", action_status="done", updated_at=newest),
        _record(
            "action-2",
            action_status="in_progress",
            updated_at=newest - timedelta(minutes=1),
        ),
        _record(
            "action-1",
            action_status="done",
            updated_at=newest - timedelta(minutes=2),
        ),
    ]
    service = ActionMemoryService(_ActionStore(records=records))

    page = asyncio.run(
        service.list_actions(
            user_id="user-1",
            project_id="project-1",
            action_statuses=["done", "in_progress"],
            limit=2,
        )
    )

    assert [item.action_id for item in page.items] == ["action-3", "action-2"]
    cursor = decode_memory_cursor(
        page.next_cursor or "",
        expected_collection="actions",
    )
    assert cursor.updated_at == records[1].updated_at
    assert cursor.record_id == "action-2"
    assert cursor.action_statuses == ["in_progress", "done"]


def test_action_service_passes_matching_cursor_keyset_to_store() -> None:
    updated_at = datetime(2026, 9, 18, 11, 0, tzinfo=UTC)
    cursor = encode_memory_cursor(
        MemoryPageCursor(
            collection="actions",
            updated_at=updated_at,
            record_id="action-7",
            action_statuses=["in_progress", "done"],
        )
    )
    store = _ActionStore()

    asyncio.run(
        ActionMemoryService(store).list_actions(
            user_id="user-1",
            project_id="project-1",
            action_statuses=["done", "in_progress"],
            limit=5,
            cursor=cursor,
        )
    )

    assert store.calls[0]["limit"] == 6
    assert store.calls[0]["after_updated_at"] == updated_at
    assert store.calls[0]["after_action_id"] == "action-7"


def test_action_service_rejects_cursor_when_status_filter_changes() -> None:
    cursor = encode_memory_cursor(
        MemoryPageCursor(
            collection="actions",
            updated_at=datetime(2026, 9, 18, 11, 0, tzinfo=UTC),
            record_id="action-7",
            action_statuses=["done"],
        )
    )

    with pytest.raises(ActionMemoryServiceError) as caught:
        asyncio.run(
            ActionMemoryService(_ActionStore()).list_actions(
                user_id="user-1",
                project_id="project-1",
                action_statuses=["todo"],
                cursor=cursor,
            )
        )

    assert caught.value.error_code == "INVALID_MEMORY_QUERY"


@pytest.mark.parametrize(
    "statuses",
    [[], ["unknown"], [""], ["todo,done"], [1]],
)
def test_action_service_rejects_invalid_statuses(statuses) -> None:
    with pytest.raises(ActionMemoryServiceError) as caught:
        asyncio.run(
            ActionMemoryService(_ActionStore()).list_actions(
                user_id="user-1",
                project_id="project-1",
                action_statuses=statuses,
            )
        )

    assert caught.value.error_code == "INVALID_MEMORY_QUERY"


@pytest.mark.parametrize("limit", [0, 101, True, 1.0, "2"])
def test_action_service_rejects_non_strict_or_out_of_range_limit(limit) -> None:
    with pytest.raises(ActionMemoryServiceError) as caught:
        asyncio.run(
            ActionMemoryService(_ActionStore()).list_actions(
                user_id="user-1",
                project_id="project-1",
                limit=limit,
            )
        )

    assert caught.value.error_code == "INVALID_MEMORY_QUERY"


def test_action_service_rejects_decision_cursor() -> None:
    cursor = encode_memory_cursor(
        MemoryPageCursor(
            collection="decisions",
            updated_at=datetime(2026, 9, 18, 11, 0, tzinfo=UTC),
            record_id="decision-7",
        )
    )

    with pytest.raises(ActionMemoryServiceError) as caught:
        asyncio.run(
            ActionMemoryService(_ActionStore()).list_actions(
                user_id="user-1",
                project_id="project-1",
                cursor=cursor,
            )
        )

    assert caught.value.error_code == "INVALID_MEMORY_QUERY"


def test_action_service_converts_store_failure_to_safe_error() -> None:
    service = ActionMemoryService(
        _ActionStore(error=RuntimeError("postgres password=secret"))
    )

    with pytest.raises(ActionMemoryServiceError) as caught:
        asyncio.run(
            service.list_actions(user_id="user-1", project_id="project-1")
        )

    assert caught.value.error_code == "MEMORY_STORE_UNAVAILABLE"
    assert "secret" not in caught.value.error_reason


def test_action_service_summarizes_default_pending_statuses() -> None:
    store = _ActionStore()

    summary = asyncio.run(
        ActionMemoryService(store).summarize_actions(
            user_id=" user-1 ",
            project_id=" project-1 ",
        )
    )

    assert summary.count == 3
    assert store.calls == [
        {
            "user_id": "user-1",
            "project_id": "project-1",
            "action_statuses": ["todo", "in_progress", "blocked"],
        }
    ]


def test_action_service_rejects_missing_cursor_timestamp_for_next_page() -> None:
    records = [
        _record("action-2", updated_at=None),
        _record("action-1", updated_at=None),
    ]

    with pytest.raises(ActionMemoryServiceError) as caught:
        asyncio.run(
            ActionMemoryService(_ActionStore(records=records)).list_actions(
                user_id="user-1",
                project_id="project-1",
                limit=1,
            )
        )

    assert caught.value.error_code == "MEMORY_QUERY_FAILED"
