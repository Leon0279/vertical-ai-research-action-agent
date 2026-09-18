"""Tests for the Decision Memory application service."""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from app.common.utils.memory_cursor import decode_memory_cursor, encode_memory_cursor
from app.domain.models import DecisionMemoryRecord
from app.domain.models.memory.memory_page_cursor import MemoryPageCursor
from app.services.memory.decision_memory_service import DecisionMemoryService
from app.services.memory.decision_memory_service_error import (
    DecisionMemoryServiceError,
)


class _DecisionStore:
    def __init__(
        self,
        *,
        records: list[DecisionMemoryRecord] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.records = records or []
        self.error = error
        self.calls: list[dict[str, object]] = []

    async def list_active_decisions_page(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.records


def _record(
    decision_id: str,
    *,
    updated_at: datetime | None,
) -> DecisionMemoryRecord:
    return DecisionMemoryRecord(
        decision_id=decision_id,
        user_id="user-1",
        project_id="project-1",
        decision_title=f"Decision {decision_id}",
        record_status="active",
        updated_at=updated_at,
    )


def test_decision_service_returns_empty_page_and_requests_limit_plus_one() -> None:
    store = _DecisionStore()
    service = DecisionMemoryService(store)

    page = asyncio.run(
        service.list_active_decisions(
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
            "limit": 21,
            "after_updated_at": None,
            "after_decision_id": None,
        }
    ]


def test_decision_service_builds_next_cursor_from_last_returned_item() -> None:
    newest = datetime(2026, 9, 18, 12, 0, tzinfo=UTC)
    records = [
        _record("decision-3", updated_at=newest),
        _record("decision-2", updated_at=newest - timedelta(minutes=1)),
        _record("decision-1", updated_at=newest - timedelta(minutes=2)),
    ]
    service = DecisionMemoryService(_DecisionStore(records=records))

    page = asyncio.run(
        service.list_active_decisions(
            user_id="user-1",
            project_id="project-1",
            limit=2,
        )
    )

    assert [item.decision_id for item in page.items] == ["decision-3", "decision-2"]
    assert page.next_cursor is not None
    cursor = decode_memory_cursor(
        page.next_cursor,
        expected_collection="decisions",
    )
    assert cursor.updated_at == records[1].updated_at
    assert cursor.record_id == "decision-2"


def test_decision_service_passes_decoded_keyset_to_store() -> None:
    updated_at = datetime(2026, 9, 18, 11, 0, tzinfo=UTC)
    cursor = encode_memory_cursor(
        MemoryPageCursor(
            collection="decisions",
            updated_at=updated_at,
            record_id="decision-7",
        )
    )
    store = _DecisionStore()
    service = DecisionMemoryService(store)

    asyncio.run(
        service.list_active_decisions(
            user_id="user-1",
            project_id="project-1",
            limit=5,
            cursor=cursor,
        )
    )

    assert store.calls[0]["limit"] == 6
    assert store.calls[0]["after_updated_at"] == updated_at
    assert store.calls[0]["after_decision_id"] == "decision-7"


@pytest.mark.parametrize("limit", [0, 101, True, 1.0, "2"])
def test_decision_service_rejects_non_strict_or_out_of_range_limit(limit) -> None:
    service = DecisionMemoryService(_DecisionStore())

    with pytest.raises(DecisionMemoryServiceError) as caught:
        asyncio.run(
            service.list_active_decisions(
                user_id="user-1",
                project_id="project-1",
                limit=limit,
            )
        )

    assert caught.value.error_code == "INVALID_MEMORY_QUERY"


@pytest.mark.parametrize("cursor", ["", "   ", "broken%%%", "x" * 4097])
def test_decision_service_rejects_invalid_cursor(cursor: str) -> None:
    service = DecisionMemoryService(_DecisionStore())

    with pytest.raises(DecisionMemoryServiceError) as caught:
        asyncio.run(
            service.list_active_decisions(
                user_id="user-1",
                project_id="project-1",
                cursor=cursor,
            )
        )

    assert caught.value.error_code == "INVALID_MEMORY_QUERY"


def test_decision_service_converts_store_failure_to_safe_error() -> None:
    service = DecisionMemoryService(
        _DecisionStore(error=RuntimeError("postgres password=secret"))
    )

    with pytest.raises(DecisionMemoryServiceError) as caught:
        asyncio.run(
            service.list_active_decisions(
                user_id="user-1",
                project_id="project-1",
            )
        )

    assert caught.value.error_code == "MEMORY_STORE_UNAVAILABLE"
    assert "secret" not in caught.value.error_reason


def test_decision_service_rejects_missing_cursor_timestamp_for_next_page() -> None:
    records = [
        _record("decision-2", updated_at=None),
        _record("decision-1", updated_at=None),
    ]
    service = DecisionMemoryService(_DecisionStore(records=records))

    with pytest.raises(DecisionMemoryServiceError) as caught:
        asyncio.run(
            service.list_active_decisions(
                user_id="user-1",
                project_id="project-1",
                limit=1,
            )
        )

    assert caught.value.error_code == "MEMORY_QUERY_FAILED"
