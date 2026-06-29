"""docs_search 检索响应模型。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.domain.models.docs_search.docs_search_result import DocsSearchResult


class DocsSearchResponse(BaseModel):
    """表示 docs_search adapter 的标准化响应容器。"""

    results: list[DocsSearchResult] = Field(
        default_factory=list,
        description=(
            "optional 字段，默认空列表。标准化 docs 检索结果列表。"
            "列表中的每一项都是可供下游 tool 层消费的 DocsSearchResult。"
        ),
    )
    dropped_item_count: int = Field(
        default=0,
        ge=0,
        description=(
            "optional 字段，默认值为 0。manifest 解析或标准化过程中被丢弃的条目数量。"
            "通常表示 llms.txt 中存在格式不合法、URL 不允许或缺关键字段的条目。"
        ),
    )
    source_summary: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "optional 字段，默认空 dict。对本次 docs 搜索来源与结果的摘要信息，"
            "当前主要包含：selected_family、selected_tool、searched_sources、normalized_count。"
        ),
    )
