"""单次 retrieval attempt 的轻量轨迹模型。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, Field, model_validator

from app.domain.enums import AcquisitionStatus, FamilyName


class RetrievalAttemptTrace(BaseModel):
    """Tool Execution Layer 中一次 family execution attempt 的摘要。

    当前项目中该模型主要由 ToolExecutionLayerService 写入 RetrievalTrace.attempts，
    用于记录 retry/fallback 前后的每次尝试。docs tool 当前通常不直接创建该对象。
    """

    selected_family: FamilyName | None = Field(
        default=None,
        description=(
            "可选字段。本次 attempt 执行的 retrieval family。当前项目中有用：TEL 会写入 docs_search、paper_search、"
            "web_search 或 research_knowledge_recall，用于解释 fallback 前后 family 是否发生变化。"
        ),
    )
    generated_query: str | None = Field(
        default=None,
        description=(
            "可选字段。本次 attempt 使用的 generated query。当前项目中有用：TEL 会记录 query generation 的结果；"
            "retry_same_tool 通常复用同一 query，fallback_to_broader_search 通常会为新 family 重新生成 query。"
        ),
    )
    query_focus: str | None = Field(
        default=None,
        description=(
            "可选字段。本次 attempt query 的 focus。当前项目中有用：由 RetrievalQueryGenerationService 生成并经 TEL 记录，"
            "用于解释 query 为什么这样写。"
        ),
    )
    acquisition_status: AcquisitionStatus | None = Field(
        default=None,
        description=(
            "可选字段。本次 family/tool 执行返回的 acquisition status。当前项目中有用：TEL 会记录 success、partial_success、"
            "no_result 或 failed，以便观察 recovery 前后的结果变化。"
        ),
    )
    evaluation_status: str | None = Field(
        default=None,
        description=(
            "可选字段。本次 attempt 之后 RequestCompletionEvaluationService 的 evaluation_status。当前项目中有用："
            "TEL 用它区分 evaluation 是否成功产出 recovery decision。"
        ),
    )
    recovery_action: str | None = Field(
        default=None,
        description=(
            "可选字段。本次 evaluation 建议的 recovery action。当前项目中有用：可能为 stop、continue、retry_same_tool、"
            "fallback 等；TEL 会根据该信号决定是否继续 bounded recovery。"
        ),
    )
    next_step_hint: str | None = Field(
        default=None,
        description=(
            "可选字段。本次 evaluation 给出的下一步提示。当前项目中有用：可能为 none、continue_current_request、"
            "retry_same_tool、fallback_within_same_family、fallback_to_broader_search、stop_request。"
        ),
    )
    retry_count: int = Field(
        default=0,
        ge=0,
        description=(
            "可选字段，默认 0，必须大于等于 0。本次 attempt 发生时 TEL 已消耗的 retry 次数。当前项目中有用："
            "用于观察 retry budget 是否被消费，以及最终结果来自第几次 retry。"
        ),
    )
    fallback_applied: bool = Field(
        default=False,
        description=(
            "可选字段，默认 False。本次 attempt 发生时 broader-family fallback 是否已经被应用。当前项目中有用："
            "用于区分初始 family attempt 与 fallback 后的新 family attempt。"
        ),
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "可选字段，默认空 dict。本次 attempt 的扩展信息。当前项目中有用但不是稳定主字段。"
            "兼容旧 dict 输入时，除 selected_family、generated_query、query_focus、acquisition_status、"
            "evaluation_status、recovery_action、next_step_hint、retry_count、fallback_applied、metadata 之外的 key "
            "会被收拢到这里。可用于记录 attempt-specific debug 信息，例如 family/tool 错误摘要或临时诊断字段。"
        ),
    )

    @model_validator(mode="before")
    @classmethod
    def _from_legacy_mapping(cls, value: Any) -> Any:
        if isinstance(value, cls) or not isinstance(value, Mapping):
            return value
        known = {
            "selected_family",
            "generated_query",
            "query_focus",
            "acquisition_status",
            "evaluation_status",
            "recovery_action",
            "next_step_hint",
            "retry_count",
            "fallback_applied",
            "metadata",
        }
        metadata = dict(value.get("metadata") or {}) if isinstance(value.get("metadata"), Mapping) else {}
        for key, item in value.items():
            if key not in known:
                metadata[key] = item
        normalized = {
            key: value.get(key)
            for key in known
            if key != "metadata" and key in value
        }
        normalized["metadata"] = metadata
        return normalized

    def to_legacy_dict(self) -> dict[str, Any]:
        data = self.model_dump(exclude={"metadata"})
        data.update(self.metadata)
        return data
