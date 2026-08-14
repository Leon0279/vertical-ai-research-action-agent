"""Contract for research executor services."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.models import ResearchStageInput, ResearchStageResult


@runtime_checkable
class ResearchExecutorProtocol(Protocol):
    """定义研究执行器的抽象交互契约。

Executes the evidence-driven research loop."""

    async def execute(self, stage_input: ResearchStageInput) -> ResearchStageResult:
        """执行研究阶段的有限轮证据驱动流程。

        Args:
            stage_input (ResearchStageInput): 由 pipeline 从执行上下文投影出的研究目标、规划参考、补充上下文和运行时限制。

        Returns:
            ResearchStageResult: 研究阶段产出的来源引用、证据摘要、中间发现、开放问题、执行状态与轮次数。
        """
        ...
