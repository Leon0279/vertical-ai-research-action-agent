"""Shared utility helpers."""

from app.common.utils.hashing import sha1_hex
from app.common.utils.ids import generate_session_id, generate_trace_id
from app.common.utils.json_utils import (
    is_json_serializable,
    load_json_string_list,
    strip_json_code_fence,
)
from app.common.utils.parsing import parse_optional_iso_datetime
from app.common.utils.text import (
    normalize_whitespace_or_none,
    strip_or_none,
    strip_optional_string,
    unique_non_empty_strings,
)
from app.common.utils.urls import is_absolute_http_url

__all__ = [
    "generate_session_id",
    "generate_trace_id",
    "is_absolute_http_url",
    "is_json_serializable",
    "load_json_string_list",
    "normalize_whitespace_or_none",
    "parse_optional_iso_datetime",
    "sha1_hex",
    "strip_json_code_fence",
    "strip_or_none",
    "strip_optional_string",
    "unique_non_empty_strings",
]
