"""Deterministic non-secret hashing helpers."""

from __future__ import annotations

import hashlib


def sha1_hex(value: str) -> str:
    """返回 UTF-8 文本的 SHA-1 十六进制摘要，用于稳定的非安全标识。"""

    return hashlib.sha1(value.encode("utf-8")).hexdigest()
