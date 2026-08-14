"""Execution guardrail settings."""

from dataclasses import dataclass


@dataclass(slots=True)
class ExecutionGuardrails:
    """Budget and boundary settings for research execution."""

    # 单次 ResearchExecutorService.execute 调用允许执行的最大 research iteration 数。
    max_iterations: int = 2
    # 单次 research run 可消耗的最大工具调用次数，用于限制 retrieval 成本和恢复循环。
    max_tool_calls: int = 5
    # 单次 research run 最多保留的结构化 evidence item 数量，避免 working state 无界增长。
    max_evidence_items: int = 20
