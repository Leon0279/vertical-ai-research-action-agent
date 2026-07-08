"""Retrieval family name enum."""

from __future__ import annotations

from enum import StrEnum


class FamilyName(StrEnum):
    """当前项目支持的 retrieval family 名称。

    该枚举用于替代散落在 request/result/service 中的 family name 字符串。
    使用 StrEnum 是为了保持字符串输入兼容、字符串比较兼容，以及 JSON 输出仍为
    research_knowledge_recall / docs_search / paper_search / web_search 这些 wire value。
    """

    RESEARCH_KNOWLEDGE_RECALL = "research_knowledge_recall"
    DOCS_SEARCH = "docs_search"
    PAPER_SEARCH = "paper_search"
    WEB_SEARCH = "web_search"
