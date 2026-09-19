"""Tests for opaque Memory pagination cursors."""

import base64
import json
from datetime import UTC, datetime

import pytest

from app.common.utils.memory_cursor import decode_memory_cursor, encode_memory_cursor
from app.domain.models.memory.memory_page_cursor import MemoryPageCursor


def test_memory_cursor_round_trip_is_url_safe_and_stable() -> None:
    cursor = MemoryPageCursor(
        collection="decisions",
        updated_at=datetime(2026, 9, 18, 10, 30, tzinfo=UTC),
        record_id="decision-2",
    )

    encoded = encode_memory_cursor(cursor)
    decoded = decode_memory_cursor(encoded, expected_collection="decisions")

    assert decoded == cursor
    assert "=" not in encoded
    assert set(encoded) <= set(
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
    )


def test_action_memory_cursor_round_trip_preserves_status_filter() -> None:
    cursor = MemoryPageCursor(
        collection="actions",
        updated_at=datetime(2026, 9, 18, 10, 30, tzinfo=UTC),
        record_id="action-2",
        action_statuses=["in_progress", "done"],
    )

    encoded = encode_memory_cursor(cursor)
    decoded = decode_memory_cursor(encoded, expected_collection="actions")

    assert decoded == cursor
    with pytest.raises(ValueError, match="collection mismatch"):
        decode_memory_cursor(encoded, expected_collection="decisions")


def test_policy_memory_cursor_round_trip_is_collection_bound() -> None:
    cursor = MemoryPageCursor(
        collection="policies",
        updated_at=datetime(2026, 9, 19, 10, 30, tzinfo=UTC),
        record_id="policy-2",
    )

    encoded = encode_memory_cursor(cursor)
    decoded = decode_memory_cursor(encoded, expected_collection="policies")

    assert decoded == cursor
    with pytest.raises(ValueError, match="collection mismatch"):
        decode_memory_cursor(encoded, expected_collection="actions")


def test_research_knowledge_cursor_round_trip_preserves_visibility_scopes() -> None:
    cursor = MemoryPageCursor(
        collection="research_knowledge",
        updated_at=datetime(2026, 9, 19, 10, 30, tzinfo=UTC),
        record_id="knowledge-2",
        visibility_scopes=["user", "project"],
    )

    encoded = encode_memory_cursor(cursor)
    decoded = decode_memory_cursor(
        encoded,
        expected_collection="research_knowledge",
    )

    assert decoded == cursor
    with pytest.raises(ValueError, match="collection mismatch"):
        decode_memory_cursor(encoded, expected_collection="policies")


@pytest.mark.parametrize(
    "value",
    [
        "not-valid-%%%",
        base64.urlsafe_b64encode(b"not-json").decode("ascii"),
        base64.urlsafe_b64encode(
            json.dumps(
                {
                    "version": 2,
                    "collection": "decisions",
                    "updated_at": "2026-09-18T10:30:00Z",
                    "record_id": "decision-2",
                }
            ).encode()
        ).decode("ascii"),
        base64.urlsafe_b64encode(
            json.dumps(
                {
                    "version": 1,
                    "collection": "actions",
                    "updated_at": "2026-09-18T10:30:00Z",
                    "record_id": "action-2",
                }
            ).encode()
        ).decode("ascii"),
    ],
)
def test_memory_cursor_rejects_malformed_or_incompatible_values(value: str) -> None:
    with pytest.raises(ValueError, match="cursor"):
        decode_memory_cursor(value, expected_collection="decisions")


def test_memory_cursor_rejects_naive_timestamp() -> None:
    with pytest.raises(ValueError, match="timezone"):
        MemoryPageCursor(
            collection="decisions",
            updated_at=datetime(2026, 9, 18, 10, 30),
            record_id="decision-2",
        )


def test_memory_cursor_rejects_collection_specific_filter_mismatch() -> None:
    with pytest.raises(ValueError, match="decision cursors"):
        MemoryPageCursor(
            collection="decisions",
            updated_at=datetime(2026, 9, 18, 10, 30, tzinfo=UTC),
            record_id="decision-2",
            action_statuses=["todo"],
        )

    with pytest.raises(ValueError, match="at least one"):
        MemoryPageCursor(
            collection="actions",
            updated_at=datetime(2026, 9, 18, 10, 30, tzinfo=UTC),
            record_id="action-2",
        )

    with pytest.raises(ValueError, match="unique"):
        MemoryPageCursor(
            collection="actions",
            updated_at=datetime(2026, 9, 18, 10, 30, tzinfo=UTC),
            record_id="action-2",
            action_statuses=["todo", "todo"],
        )

    with pytest.raises(ValueError, match="policy cursors"):
        MemoryPageCursor(
            collection="policies",
            updated_at=datetime(2026, 9, 18, 10, 30, tzinfo=UTC),
            record_id="policy-2",
            action_statuses=["todo"],
        )

    with pytest.raises(ValueError, match="at least one"):
        MemoryPageCursor(
            collection="research_knowledge",
            updated_at=datetime(2026, 9, 18, 10, 30, tzinfo=UTC),
            record_id="knowledge-2",
        )

    with pytest.raises(ValueError, match="unique"):
        MemoryPageCursor(
            collection="research_knowledge",
            updated_at=datetime(2026, 9, 18, 10, 30, tzinfo=UTC),
            record_id="knowledge-2",
            visibility_scopes=["project", "project"],
        )

    with pytest.raises(ValueError, match="decision cursors"):
        MemoryPageCursor(
            collection="decisions",
            updated_at=datetime(2026, 9, 18, 10, 30, tzinfo=UTC),
            record_id="decision-2",
            visibility_scopes=["project"],
        )
