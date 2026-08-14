"""Contract for Tool Execution Layer coordination."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.models import ToolExecutionLayerRequest, ToolExecutionLayerResult


@runtime_checkable
class ToolExecutionLayerServiceProtocol(Protocol):
    """定义工具执行层服务的抽象交互契约。

Research Executor-facing Tool Execution Layer service interface."""

    async def execute(
        self,
        request: ToolExecutionLayerRequest,
    ) -> ToolExecutionLayerResult:
        """在预算范围内编排 family 选择、查询生成、检索执行与完成度评估。

        Args:
            request (ToolExecutionLayerRequest): 研究执行器发起的检索请求，包含 evidence intent、family 约束、范围与执行预算。

        Returns:
            ToolExecutionLayerResult: 最终 family 结果、归一化候选材料、执行尝试轨迹、完成度评估与整体状态。
        """
