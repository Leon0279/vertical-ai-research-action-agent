"""Contract for response assembler services."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.models import ExecutionContext, StructuredOutput


@runtime_checkable
class ResponseAssemblerProtocol(Protocol):
    """定义响应组装器的抽象交互契约。

Assembles final user-facing outputs."""

    async def assemble(self, context: ExecutionContext) -> StructuredOutput:
        """将已写入执行上下文的结论状态组装为上游可直接返回的结构化响应。

        Args:
            context (ExecutionContext): 已完成各阶段处理的执行上下文，重点读取其中的最终答案、摘要、引用和行动项。

        Returns:
            StructuredOutput: 面向调用方和用户的最终结构化输出。
        """
