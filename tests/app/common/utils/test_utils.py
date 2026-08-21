"""Tests for shared utility helpers."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.common.utils import (
    is_absolute_http_url,
    is_json_serializable,
    load_json_string_list,
    normalize_whitespace_or_none,
    parse_optional_iso_datetime,
    sha1_hex,
    strip_json_code_fence,
    strip_or_none,
    strip_optional_string,
    unique_non_empty_strings,
)


def test_text_helpers_normalize_expected_values() -> None:
    assert strip_or_none("  value  ") == "value"
    assert strip_or_none(123) is None
    assert strip_optional_string(123) == 123
    assert normalize_whitespace_or_none(" a\n  b\t c ") == "a b c"
    assert normalize_whitespace_or_none(None) is None
    assert unique_non_empty_strings([" a ", "", "a", 3, "b "]) == ["a", "b"]


def test_json_helpers_preserve_fence_and_decoding_semantics() -> None:
    assert strip_json_code_fence("```json\n{\"key\": 1}\n```") == '{"key": 1}'
    assert strip_json_code_fence("```\n{\"key\": 1}") == '```\n{"key": 1}'
    assert (
        strip_json_code_fence("```\n{\"key\": 1}", allow_unterminated=True)
        == '{"key": 1}'
    )
    assert (
        strip_json_code_fence("```python\n{\"key\": 1}\n```", json_only=True)
        == 'python\n{"key": 1}'
    )
    assert strip_json_code_fence("```json {\"key\": 1} ```", json_only=True) == '{"key": 1}'
    assert load_json_string_list('["a", 2]') == ["a", "2"]
    assert load_json_string_list(["a", 2]) == ["a", "2"]
    with pytest.raises(TypeError, match="JSON array"):
        load_json_string_list('{"key": "value"}')
    assert is_json_serializable({"key": ["value"]}) is True
    assert is_json_serializable({"items": {"not-json-safe"}}) is False


def test_parsing_url_and_hash_helpers_are_deterministic() -> None:
    assert parse_optional_iso_datetime("2026-08-21T08:00:00Z") == datetime(
        2026,
        8,
        21,
        8,
        0,
        tzinfo=UTC,
    )
    assert parse_optional_iso_datetime("not-a-date") is None
    assert is_absolute_http_url("https://example.test/path") is True
    assert is_absolute_http_url("relative/path") is False
    assert sha1_hex("https://example.test") == sha1_hex("https://example.test")
