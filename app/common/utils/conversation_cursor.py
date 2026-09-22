"""Opaque URL-safe cursor encoding for conversation history pagination."""

from __future__ import annotations

import base64
import binascii
import json
from typing import Literal

from pydantic import ValidationError

from app.domain.models.conversation.conversation_page_cursor import (
    ConversationPageCursor,
)


def encode_conversation_cursor(cursor: ConversationPageCursor) -> str:
    """将已校验的 conversation cursor 编码为 URL-safe Base64 JSON。

    Args:
        cursor (ConversationPageCursor): 包含集合、排序位置和可选 session 作用域的已校验 cursor。

    Returns:
        str: 可安全放入 HTTP query parameter 的 opaque cursor 字符串。
    """

    payload = json.dumps(
        cursor.model_dump(mode="json"),
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def decode_conversation_cursor(
    value: str,
    *,
    expected_collection: Literal["sessions", "messages"],
    expected_session_id: str | None = None,
) -> ConversationPageCursor:
    """解码并校验 collection 与 session 作用域绑定的 conversation cursor。

    Args:
        value (str): 客户端传回的 opaque cursor 字符串。
        expected_collection (Literal["sessions", "messages"]): 当前查询允许使用的 cursor 集合。
        expected_session_id (str | None): Message 查询预期绑定的 session 标识；session 列表查询为 None。

    Returns:
        ConversationPageCursor: 解码、schema 校验并完成作用域检查的分页位置。

    Raises:
        ValueError: Cursor 损坏、版本/schema 不合法、集合不匹配或 session 作用域不匹配。
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
        cursor = ConversationPageCursor.model_validate(raw_payload)
    except (
        UnicodeEncodeError,
        UnicodeDecodeError,
        binascii.Error,
        json.JSONDecodeError,
        TypeError,
        ValidationError,
    ) as exc:
        raise ValueError("Invalid conversation pagination cursor.") from exc

    if cursor.collection != expected_collection:
        raise ValueError("Conversation pagination cursor collection mismatch.")
    if expected_collection == "messages" and cursor.session_id != expected_session_id:
        raise ValueError("Conversation message cursor session mismatch.")
    return cursor
