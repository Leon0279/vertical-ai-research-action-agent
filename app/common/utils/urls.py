"""URL validation helpers."""

from __future__ import annotations

from urllib.parse import urlparse


def is_absolute_http_url(value: str) -> bool:
    """判断字符串是否为带主机名的绝对 HTTP(S) URL。"""

    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
