"""Domain model for request completion and recovery evaluation requests."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.domain.enums import FamilyName
from app.domain.models.families.base_family_execution_result import (
    BaseFamilyExecutionResult,
)

FailureReason = Literal[
    "timeout",
    "tool_error",
    "rate_limited",
    "malformed_response",
    "tool_unavailable",
    "auth_error",
    "invalid_request",
    "unknown_error",
]

FallbackPolicy = Literal[
    "no_fallback",
    "fallback_within_same_family",
    "fallback_to_broader_search",
]


class RequestCompletionEvaluationRequest(BaseModel):
    """表示请求完成度评估的输入请求。

Input for evaluating request completion and recovery need after one execution."""

    target_problem: str = Field(
        description="必填字段。本次 Tool Execution Layer attempt 要解决的当前 retrieval target problem。",
    )
    selected_family: FamilyName = Field(
        description="必填字段。当前被评估 execution outcome 所使用的 retrieval family。",
    )
    generated_query: str | None = Field(
        default=None,
        description="可选字段。已执行 family 使用的 generated query；没有生成或无法获得时为 None。",
    )
    execution_outcome: BaseFamilyExecutionResult = Field(
        description="必填字段。需要评估完成度与恢复需求的统一 family execution result。",
    )
    failure_reason: FailureReason | None = Field(
        default=None,
        description="可选字段。当 acquisition_status 为 failed 时的归一化失败原因；正常路径时为 None。",
    )
    continuation_available: bool = Field(
        default=False,
        description="当前请求是否可以不新开轮次而继续执行；用于 evaluator 判断恢复可行性。",
    )
    retry_budget: int = Field(
        default=1,
        description="当前请求允许的同一 tool 最大重试次数。",
    )
    retry_count: int = Field(
        default=0,
        description="当前请求已经消耗的同一 tool 重试次数。",
    )
    fallback_policy: FallbackPolicy = Field(
        default="fallback_within_same_family",
        description="控制是否允许 same-family 或 broader-family fallback 的恢复策略。",
    )
    fallback_applied: bool = Field(
        default=False,
        description="当前请求链是否已经使用过 fallback 路径，用于避免重复回退。",
    )
    max_results: int | None = Field(
        default=None,
        description="可选字段。当前请求 normalized retrieval item 的数量上限；未限制时为 None。",
    )
    timeout_limit_ms: int | None = Field(
        default=None,
        description="可选字段。当前请求范围内的超时预算，单位毫秒；未设置时为 None。",
    )
    request_elapsed_ms: int | None = Field(
        default=None,
        description="可选字段。当前请求已消耗的执行时间，单位毫秒；未知时为 None。",
    )
    available_families: list[FamilyName] = Field(
        default_factory=list,
        description="可选字段，默认空列表。当前 runtime 可供 recovery/fallback 选择的 retrieval families。",
    )
    allowed_source_families: list[FamilyName] = Field(
        default_factory=list,
        description="可选字段，默认空列表。限制 fallback 可选 retrieval family 的 allow-list；为空时不额外限制。",
    )
    blocked_source_families: list[FamilyName] = Field(
        default_factory=list,
        description="可选字段，默认空列表。排除 fallback 候选 retrieval family 的 block-list。",
    )
