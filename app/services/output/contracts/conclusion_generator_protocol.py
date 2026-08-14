"""Contract for conclusion generator services."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.models import ExecutionContext


@runtime_checkable
class ConclusionGeneratorProtocol(Protocol):
    """定义结论Generator的抽象交互契约。

Generates structured conclusion payloads."""

    async def generate(self, context: ExecutionContext) -> None:
        """基于研究阶段产物生成面向用户的最终结论，并原地写回执行上下文。

        Args:
            context (ExecutionContext): 包含研究证据、来源、中间发现、开放问题和任务约束的当前执行上下文。

        Returns:
            None: 不返回结论对象；最终答案、摘要、推荐、行动项、引用、置信度和注意事项写入 context.running_state。
        """
        ...
