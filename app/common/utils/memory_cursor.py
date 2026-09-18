"""Opaque URL-safe cursor encoding for Memory keyset pagination."""

from __future__ import annotations

import base64
import binascii
import json
from typing import Literal

from pydantic import ValidationError

from app.domain.models.memory.memory_page_cursor import MemoryPageCursor


def encode_memory_cursor(cursor: MemoryPageCursor) -> str:
    """Encode a validated cursor as unpadded URL-safe Base64 JSON."""

    payload = json.dumps(
        cursor.model_dump(mode="json"),
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def decode_memory_cursor(
    value: str,
    *,
    expected_collection: Literal["decisions"],
) -> MemoryPageCursor:
    """Decode and validate a collection-bound versioned Memory cursor.

    Raises:
        ValueError: The cursor is malformed, unsupported, or belongs to another
            collection.
    """

    try:
        encoded = value.encode("ascii")
        padding = b"=" * (-len(encoded) % 4)
        decoded = base64.b64decode(
            encoded + padding,
            altchars=b"-_",
            validate=True,
        )
        raw_payload = json.loads(decoded.decode("utf-8"))
        cursor = MemoryPageCursor.model_validate(raw_payload)
    except (
        UnicodeEncodeError,
        UnicodeDecodeError,
        binascii.Error,
        json.JSONDecodeError,
        TypeError,
        ValidationError,
    ) as exc:
        raise ValueError("Invalid memory pagination cursor.") from exc

    if cursor.collection != expected_collection:
        raise ValueError("Memory pagination cursor collection mismatch.")
    return cursor
