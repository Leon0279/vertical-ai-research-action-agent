"""docs_search 查询输入模型。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class DocsSearchQuery(BaseModel):
    """表示 docs_search adapter 的标准化查询输入。"""

    query_text: str = Field(
        min_length=1,
        description=(
            "必填字段。当前请求要用于文档检索的查询文本。"
            "这是 docs_search adapter 的主查询输入，不应为空字符串。"
        ),
    )
    target_problem: str | None = Field(
        default=None,
        description=(
            "optional 字段。触发这次检索的上层目标问题或任务背景。"
            "用于帮助 adapter 在打分时结合更高层问题理解当前 query。"
        ),
    )
    limit: int = Field(
        default=5,
        description=(
            "optional 字段，默认值为 5。期望返回的 docs 检索结果最大数量。"
            "最终仍会受到 adapter 自身配置上限约束。"
        ),
    )
    freshness_requirement: str | None = Field(
        default=None,
        description=(
            "optional 字段。来自上游 acquisition intent 的时效性提示，"
            "例如 recent、latest 一类要求；当前 llms.txt docs adapter 主要透传和保留该语义。"
        ),
    )
    breadth: str | None = Field(
        default=None,
        description=(
            "optional 字段。检索范围提示，例如 narrow 或 broad。"
            "当前用于表达期望的检索覆盖宽度语义。"
        ),
    )
    source_names: list[str] = Field(
        default_factory=list,
        description=(
            "optional 字段，默认空列表。允许检索的 docs source name 白名单，"
            "来源于 adapter 配置中的 source_name；为空时表示使用全部已配置 docs source。"
        ),
    )
