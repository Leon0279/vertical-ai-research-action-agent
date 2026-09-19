"""Tests for the Policy Memory application service."""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from app.common.utils.memory_cursor import decode_memory_cursor, encode_memory_cursor
from app.domain.models import MemoryCollectionSummary, PreferencePolicyMemoryRecord
from app.domain.models.memory.memory_page_cursor import MemoryPageCursor
from app.services.memory.policy_memory_service import PolicyMemoryService
from app.services.memory.policy_memory_service_error import PolicyMemoryServiceError


class _PolicyStore:
    def __init__(
        self,
        *,
        records: list[PreferencePolicyMemoryRecord] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.records = records or []
        self.error = error
        self.calls: list[dict[str, object]] = []

    async def list_policies_page(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.records

    async def summarize_policies(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return MemoryCollectionSummary(count=4)


def _record(
    policy_id: str,
    *,
    updated_at: datetime | None,
) -> PreferencePolicyMemoryRecord:
    return PreferencePolicyMemoryRecord(
        policy_id=policy_id,
        user_id="user-1",
        project_id="project-1",
        owner_scope_type="project",
        owner_scope_value="project-1",
        policy_type="format_rule",
        policy_text=f"Policy {policy_id}",
        record_status="active",
        updated_at=updated_at,
    )


def test_policy_service_returns_empty_page_and_requests_limit_plus_one() -> None:
    store = _PolicyStore()

    page = asyncio.run(
        PolicyMemoryService(store).list_policies(
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
            "after_policy_id": None,
        }
    ]


def test_policy_service_builds_next_cursor_from_last_returned_item() -> None:
    newest = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)
    records = [
        _record("policy-3", updated_at=newest),
        _record("policy-2", updated_at=newest - timedelta(minutes=1)),
        _record("policy-1", updated_at=newest - timedelta(minutes=2)),
    ]

    page = asyncio.run(
        PolicyMemoryService(_PolicyStore(records=records)).list_policies(
            user_id="user-1",
            project_id="project-1",
            limit=2,
        )
    )

    assert [item.policy_id for item in page.items] == ["policy-3", "policy-2"]
    cursor = decode_memory_cursor(
        page.next_cursor or "",
        expected_collection="policies",
    )
    assert cursor.updated_at == records[1].updated_at
    assert cursor.record_id == "policy-2"


def test_policy_service_passes_decoded_keyset_to_store() -> None:
    updated_at = datetime(2026, 9, 19, 11, 0, tzinfo=UTC)
    cursor = encode_memory_cursor(
        MemoryPageCursor(
            collection="policies",
            updated_at=updated_at,
            record_id="policy-7",
        )
    )
    store = _PolicyStore()

    asyncio.run(
        PolicyMemoryService(store).list_policies(
            user_id="user-1",
            project_id="project-1",
            limit=5,
            cursor=cursor,
        )
    )

    assert store.calls[0]["limit"] == 6
    assert store.calls[0]["after_updated_at"] == updated_at
    assert store.calls[0]["after_policy_id"] == "policy-7"


@pytest.mark.parametrize("limit", [0, 101, True, 1.0, "2"])
def test_policy_service_rejects_non_strict_or_out_of_range_limit(limit) -> None:
    with pytest.raises(PolicyMemoryServiceError) as caught:
        asyncio.run(
            PolicyMemoryService(_PolicyStore()).list_policies(
                user_id="user-1",
                project_id="project-1",
                limit=limit,
            )
        )

    assert caught.value.error_code == "INVALID_MEMORY_QUERY"


@pytest.mark.parametrize("cursor", ["", "   ", "broken%%%", "x" * 4097])
def test_policy_service_rejects_invalid_cursor(cursor: str) -> None:
    with pytest.raises(PolicyMemoryServiceError) as caught:
        asyncio.run(
            PolicyMemoryService(_PolicyStore()).list_policies(
                user_id="user-1",
                project_id="project-1",
                cursor=cursor,
            )
        )

    assert caught.value.error_code == "INVALID_MEMORY_QUERY"


def test_policy_service_rejects_cursor_from_another_collection() -> None:
    cursor = encode_memory_cursor(
        MemoryPageCursor(
            collection="decisions",
            updated_at=datetime(2026, 9, 19, 11, 0, tzinfo=UTC),
            record_id="decision-7",
        )
    )

    with pytest.raises(PolicyMemoryServiceError) as caught:
        asyncio.run(
            PolicyMemoryService(_PolicyStore()).list_policies(
                user_id="user-1",
                project_id="project-1",
                cursor=cursor,
            )
        )

    assert caught.value.error_code == "INVALID_MEMORY_QUERY"


def test_policy_service_converts_store_failure_to_safe_error() -> None:
    service = PolicyMemoryService(
        _PolicyStore(error=RuntimeError("postgres password=secret"))
    )

    with pytest.raises(PolicyMemoryServiceError) as caught:
        asyncio.run(
            service.list_policies(user_id="user-1", project_id="project-1")
        )

    assert caught.value.error_code == "MEMORY_STORE_UNAVAILABLE"
    assert "secret" not in caught.value.error_reason


def test_policy_service_summarizes_normalized_project_context() -> None:
    store = _PolicyStore()

    summary = asyncio.run(
        PolicyMemoryService(store).summarize_policies(
            user_id=" user-1 ",
            project_id=" project-1 ",
        )
    )

    assert summary.count == 4
    assert store.calls == [{"user_id": "user-1", "project_id": "project-1"}]


def test_policy_service_rejects_missing_cursor_timestamp_for_next_page() -> None:
    records = [
        _record("policy-2", updated_at=None),
        _record("policy-1", updated_at=None),
    ]

    with pytest.raises(PolicyMemoryServiceError) as caught:
        asyncio.run(
            PolicyMemoryService(_PolicyStore(records=records)).list_policies(
                user_id="user-1",
                project_id="project-1",
                limit=1,
            )
        )

    assert caught.value.error_code == "MEMORY_QUERY_FAILED"
