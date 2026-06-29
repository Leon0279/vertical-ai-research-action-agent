"""docs_search 检索结果模型。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.domain.models.source import SourceReference


class DocsSearchResult(BaseModel):
    """表示 docs_search adapter 返回的一条标准化文档检索结果。"""

    item_id: str = Field(
        min_length=1,
        description=(
            "必填字段。当前 docs search response 内部稳定的结果标识。"
            "通常由 adapter 基于 source 信息生成，用于结果去重和下游引用。"
        ),
    )
    title: str = Field(
        min_length=1,
        description=(
            "必填字段。原始文档页面或章节标题。"
            "用于展示、排序解释和后续构造 normalized retrieval item metadata。"
        ),
    )
    content: str = Field(
        min_length=1,
        description=(
            "必填字段。当前结果对应的文档片段、摘要或指导性正文内容。"
            "这是下游 tool 层会直接消费的核心文本。"
        ),
    )
    source_name: str = Field(
        min_length=1,
        description=(
            "必填字段。命中该结果的 docs source 配置名。"
            "它对应 adapter 配置中的 source_name，不等同于 publisher。"
        ),
    )
    source_reference: SourceReference = Field(
        description=(
            "必填字段。当前 docs 结果的 canonical provenance，"
            "指向原始 docs 页面或章节来源，替代旧的 source_ref/url/section 字段。"
        ),
    )
    score: float = Field(
        default=0.0,
        ge=0.0,
        description=(
            "optional 字段，默认值为 0.0。adapter 内部使用的相关性分数。"
            "该分数只在当前 docs_search adapter 内部有局部语义，不承诺跨 adapter 可比。"
        ),
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "optional 字段，默认空 dict。adapter 级附加信息，当前主要包含："
            "rank（结果排名）、manifest_summary（来自 llms.txt manifest 的摘要）、"
            "page_fetch_error（抓取页面正文失败时的错误信息，仅失败时出现）。"
        ),
    )
