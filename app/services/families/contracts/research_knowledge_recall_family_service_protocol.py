"""Contract for the research_knowledge_recall family service."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.models import (
    ResearchKnowledgeRecallFamilyRequest,
    ResearchKnowledgeRecallFamilyResult,
)


@runtime_checkable
class ResearchKnowledgeRecallFamilyServiceProtocol(Protocol):
    """定义研究知识召回检索族服务的抽象交互契约。

Runtime-facing interface for the research_knowledge_recall family service."""

    async def run(
        self,
        request: ResearchKnowledgeRecallFamilyRequest,
    ) -> ResearchKnowledgeRecallFamilyResult:
        """执行研究知识召回检索族，并返回 family 层归一化结果。

        Args:
            request (ResearchKnowledgeRecallFamilyRequest): 研究知识召回请求，包含用户边界、项目范围、查询向量或文本及召回限制。

        Returns:
            ResearchKnowledgeRecallFamilyResult: 已召回知识的归一化条目、执行摘要、追踪信息与获取状态。
        """
