"""retrieval 输出中的执行摘要模型。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, Field, model_validator


class RetrievalExecutionSummary(BaseModel):
    """跨 tool、family 和 Tool Execution Layer 使用的执行统计与 recovery 摘要。

    该模型用于描述“这次 retrieval 执行过程中发生了什么”，但不承载候选材料正文。
    当前项目中 tool 会写入基础计数，family/TEL 会补充 tool selection、retry/fallback
    等运行时信息，EvidenceProcessingService 会读取其中的上游统计用于 processing summary。
    """

    policy: str | None = Field(
        default=None,
        description=(
            "可选字段。生成该 execution summary 的策略或实现版本名称。当前项目中该字段有用：TEL 会写入 "
            "tool_execution_layer_single_request_v1 等 policy；部分 tool 当前不写该字段。它用于调试和确认 summary "
            "来自哪一版执行策略，不用于业务分支判断。"
        ),
    )
    execution_status: str | None = Field(
        default=None,
        description=(
            "可选字段。本层执行状态。当前项目中该字段有用：ToolExecutionLayerResult 可用它表达 completed/failed；"
            "tool 级结果通常主要使用 acquisition_status，因此该字段在 docs tool 中通常为空。"
        ),
    )
    normalized_count: int | None = Field(
        default=None,
        ge=0,
        description=(
            "可选字段，提供时必须大于等于 0。本层输出的 normalized item 数量。当前项目中该字段有用：docs tool "
            "会写入该字段，TEL 和 EvidenceProcessingService 可用它做统计核对；当某些旧 dict 输入未显式提供时可为空。"
        ),
    )
    dropped_item_count: int | None = Field(
        default=None,
        ge=0,
        description=(
            "可选字段，提供时必须大于等于 0。本层归一化或过滤过程中丢弃的 item 数量。当前项目中该字段有用："
            "docs tool 会写入 adapter/tool 丢弃数量；TEL 和 EvidenceProcessingService 会保留它用于解释 partial_success 或降级。"
        ),
    )
    retry_count: int = Field(
        default=0,
        ge=0,
        description=(
            "可选字段，默认 0，必须大于等于 0。TEL 在当前 bounded request 内已经消耗的 retry 次数。"
            "当前项目中该字段有用：主要由 ToolExecutionLayerService 写入；docs tool 当前通常保持默认值。"
        ),
    )
    fallback_applied: bool = Field(
        default=False,
        description=(
            "可选字段，默认 False。TEL 是否已经执行 broader-family fallback。当前项目中该字段有用："
            "ToolExecutionLayerService 在 fallback_to_broader_search 被执行后会置为 True；docs tool 当前通常保持默认值。"
        ),
    )
    recovery_attempt_count: int = Field(
        default=0,
        ge=0,
        description=(
            "可选字段，默认 0，必须大于等于 0。TEL 在当前 request 内执行过的 recovery attempt 数量。"
            "当前项目中该字段有用：用于区分首次 retrieval 与 retry/fallback 后的结果；docs tool 当前通常保持默认值。"
        ),
    )
    recovery_exhausted_reason: str | None = Field(
        default=None,
        description=(
            "可选字段。TEL 停止 recovery 的原因。当前项目中该字段有用：例如 same_family_fallback_not_executable、"
            "continue_not_executable 等；docs tool 当前通常不写入。该字段用于解释为什么 evaluator 给出 recovery signal 后没有继续执行。"
        ),
    )
    metrics: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "可选字段，默认空 dict。数值型或轻量统计指标。当前项目中有用。docs tool 当前会写入 "
            "search_result_count，表示 adapter 返回的 docs result 数量；paper/web tool 会写入 selected_for_fetch_count、"
            "fetch_success_count、fetch_empty_count、fetch_failed_count 等；memory tool 会写入 recall_result_count、"
            "used_precomputed_embedding 等。兼容旧 dict 输入时，未知的 *_count、*_ms 或 int/float 值会被归入 metrics。"
        ),
    )
    observability: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "可选字段，默认空 dict。非稳定的状态、debug 或诊断信息。当前项目中有用，但调用方不应把它当稳定业务 API。"
            "docs tool 当前通常不直接写入 observability；family/TEL 可能写入 preferred_tool_requested、needs_recovery、"
            "next_step_hint 等观测信息。兼容旧 dict 输入时，无法归入正式字段或 metrics 的未知 key 会被放到这里。"
        ),
    )

    @model_validator(mode="before")
    @classmethod
    def _from_legacy_mapping(cls, value: Any) -> Any:
        if isinstance(value, cls) or not isinstance(value, Mapping):
            return value
        known = {
            "policy",
            "execution_status",
            "normalized_count",
            "dropped_item_count",
            "retry_count",
            "fallback_applied",
            "recovery_attempt_count",
            "recovery_exhausted_reason",
            "metrics",
            "observability",
        }
        metrics = dict(value.get("metrics") or {}) if isinstance(value.get("metrics"), Mapping) else {}
        observability = (
            dict(value.get("observability") or {})
            if isinstance(value.get("observability"), Mapping)
            else {}
        )
        for key, item in value.items():
            if key in known:
                continue
            if key.endswith("_count") or key.endswith("_ms") or isinstance(item, (int, float)):
                metrics[key] = item
            else:
                observability[key] = item
        return {
            "policy": value.get("policy"),
            "execution_status": value.get("execution_status"),
            "normalized_count": value.get("normalized_count"),
            "dropped_item_count": value.get("dropped_item_count"),
            "retry_count": value.get("retry_count") or 0,
            "fallback_applied": bool(value.get("fallback_applied")),
            "recovery_attempt_count": value.get("recovery_attempt_count") or 0,
            "recovery_exhausted_reason": value.get("recovery_exhausted_reason"),
            "metrics": metrics,
            "observability": observability,
        }

    def get(self, key: str, default: Any = None) -> Any:
        """以兼容字典的方式读取执行摘要字段、metrics 或 observability 扩展字段。

        Args:
            key (str): 需要读取的执行摘要、metrics 或 observability 字段名称。
            default (Any): key 不存在时返回的默认值，默认是 None。

        Returns:
            Any: 已声明字段、metrics 或 observability 中的值，或找不到时的 default。
        """
        if hasattr(self, key):
            return getattr(self, key)
        if key in self.metrics:
            return self.metrics[key]
        return self.observability.get(key, default)

    def __getitem__(self, key: str) -> Any:
        value = self.get(key, None)
        if value is None and key not in self.metrics and key not in self.observability and not hasattr(self, key):
            raise KeyError(key)
        return value

    def __iter__(self):
        yield from self.to_legacy_dict().items()

    def to_legacy_dict(self) -> dict[str, Any]:
        """将 typed 执行摘要转换为历史兼容的扁平字典。

        Args:
            无显式业务参数。转换基于当前实例的正式字段、metrics 和 observability 完成。

        Returns:
            dict[str, Any]: 正式执行摘要、metrics 和 observability 合并后的扁平字典。
        """
        data = {
            "policy": self.policy,
            "execution_status": self.execution_status,
            "normalized_count": self.normalized_count,
            "dropped_item_count": self.dropped_item_count,
            "retry_count": self.retry_count,
            "fallback_applied": self.fallback_applied,
            "recovery_attempt_count": self.recovery_attempt_count,
            "recovery_exhausted_reason": self.recovery_exhausted_reason,
        }
        data.update(self.metrics)
        data.update(self.observability)
        return data
