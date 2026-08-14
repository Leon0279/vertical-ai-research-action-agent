"""Contract for the research_knowledge_memory tool service."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.models import (
    ResearchKnowledgeMemoryToolRequest,
    ResearchKnowledgeMemoryToolResult,
)


@runtime_checkable
class ResearchKnowledgeMemoryToolProtocol(Protocol):
    """定义研究知识记忆工具的抽象交互契约。

Runtime-facing interface for the research_knowledge_memory tool."""

    async def run(
        self,
        request: ResearchKnowledgeMemoryToolRequest,
    ) -> ResearchKnowledgeMemoryToolResult:
        """执行研究知识记忆召回，并返回归一化检索输出。

        Args:
            request (ResearchKnowledgeMemoryToolRequest): 包含用户与项目范围、查询文本或向量、召回限制和研究上下文的工具请求。

        Returns:
            ResearchKnowledgeMemoryToolResult: 归一化知识材料、来源摘要、执行统计、检索追踪与获取状态。
        """
