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
