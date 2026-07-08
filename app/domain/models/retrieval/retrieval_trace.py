"""retrieval 输出中的轻量轨迹模型。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, Field, model_validator

from app.domain.enums import FamilyName
from app.domain.models.retrieval.retrieval_attempt_trace import RetrievalAttemptTrace


class RetrievalTrace(BaseModel):
    """当前项目 retrieval 链路中共享的轻量 trace。

    该模型不是完整 tracing framework，而是供 tool、family、TEL、EvidenceProcessing
    传递最小必要检索上下文、返回来源和错误信息的结构。稳定主字段优先放在显式字段中；
    任务上下文放 context，错误放 errors，非稳定调试信息放 observability。
    """

    target_problem: str | None = Field(
        default=None,
        description=(
            "可选字段。触发本次 retrieval 的上层目标问题。当前项目中该字段有用：docs tool 会从 "
            "LlmsTxtDocsSearchToolRequest.target_problem 写入；TEL / EvidenceProcessing 可读取它作为 evidence "
            "structuring 的 target_problem 语境。"
        ),
    )
    selected_family: FamilyName | None = Field(
        default=None,
        description=(
            "可选字段。当前 retrieval 选中的 family。当前项目中该字段有用：family/TEL 通常写入该字段；"
            "docs tool 自身通常不直接写入，因为它已经位于 docs_search family 内。EvidenceProcessingService 可读取它作为 provenance fallback。"
        ),
    )
    selected_tool: str | None = Field(
        default=None,
        description=(
            "可选字段。family 内部实际执行的 tool。当前项目中该字段有用：family/TEL 会将 tool 层 selected_tool "
            "保留在 trace 中；ToolExecutionLayerResult 顶层不暴露 selected_tool，但 trace 中保留它作为 provenance。"
            "docs tool 自身通常不直接写入该字段。"
        ),
    )
    generated_query: str | None = Field(
        default=None,
        description=(
            "可选字段。TEL query generation 阶段生成的 retrieval query。当前项目中该字段有用："
            "ToolExecutionLayerService 会写入；EvidenceProcessingService 会把它写入 evidence unit metadata['generated_query']。"
            "docs tool 当前会在 context['query_text'] 中记录实际执行 query，而不是直接写 generated_query。"
        ),
    )
    query_focus: str | None = Field(
        default=None,
        description=(
            "可选字段。RetrievalQueryGenerationService 生成 query 时给出的 query focus。当前项目中该字段有用："
            "TEL 会保留它用于解释 query intent；docs tool 当前不直接写入。"
        ),
    )
    acquisition_status: str | None = Field(
        default=None,
        description=(
            "可选字段。最终 acquisition status 的 trace 副本。当前项目中该字段有用：TEL attempt trace 或上层汇总可写入；"
            "tool result 本身已有 acquisition_status 正式字段，因此 docs tool 当前通常不在 retrieval_trace 中重复写入。"
        ),
    )
    attempts: list[RetrievalAttemptTrace] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表。TEL 在一次 bounded request 内的 attempt 轨迹列表。当前项目中该字段有用："
            "ToolExecutionLayerService 会在 retry/fallback 过程中写入每次 attempt；docs tool 当前通常不直接写入 attempts。"
        ),
    )
    returned_refs: list[str] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表。本次 retrieval 返回材料的可展示/可追踪引用。当前项目中该字段有用："
            "docs tool 当前会写入每条 DocsSearchResult 的 source_reference.source_url，若无 URL 则退化为 source_id，再退化为 item_id；"
            "web/paper/memory tool 也会写入 URL、paper id、原始 source ref 等。该字段用于 trace 和人工排查，不替代 "
            "NormalizedRetrievalItem.source_references。"
        ),
    )
    errors: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "可选字段，默认空 dict。结构化但轻量的错误信息。当前项目中有用。docs tool failed 路径当前会写入 "
            "search_error；TEL 可能写入 family_exception、family_error；其它以 *_error 结尾的旧 key 在兼容转换时也会归入 errors。"
            "该字段应放简短错误摘要，不应放大型 provider raw payload 或完整 stack trace。"
        ),
    )
    context: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "可选字段，默认空 dict。检索上下文信息。当前项目中有用。docs tool 当前会写入 query_text（实际传给 adapter 的 query）"
            "和 selected_sub_source_types（实际搜索或请求约束的 docs 子来源类型）。TEL/family/memory/web 等路径可能写入 "
            "target_scope、evidence_goal、sub_question、comparison_candidate、gap、freshness_requirement、source_names、"
            "sub_source_types、include_domains、exclude_domains、owner_user_id、project_scope_id、allowed_visibility_scopes、"
            "knowledge_types、topic_tags、source_types、selected_sources、preferred_tool、candidate_tools、used_query_embedding 等。"
            "这些字段帮助后续 EvidenceProcessing 和人工诊断理解 retrieval 是在什么约束下发生的。"
        ),
    )
    observability: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "可选字段，默认空 dict。非稳定、补充性的 trace/debug 信息。当前项目中有用，但不应作为稳定业务接口消费。"
            "docs tool 当前通常不直接写入 observability；兼容旧 dict 输入时，既不是正式字段、也不属于 context/errors 的未知 key "
            "会被收拢到这里，例如 attempted_urls 等 provider/tool-specific 诊断信息。"
        ),
    )

    @model_validator(mode="before")
    @classmethod
    def _from_legacy_mapping(cls, value: Any) -> Any:
        if isinstance(value, cls) or not isinstance(value, Mapping):
            return value
        known = {
            "target_problem",
            "selected_family",
            "selected_tool",
            "generated_query",
            "query_focus",
            "acquisition_status",
            "attempts",
            "returned_refs",
            "errors",
            "context",
            "observability",
        }
        errors = dict(value.get("errors") or {}) if isinstance(value.get("errors"), Mapping) else {}
        context = dict(value.get("context") or {}) if isinstance(value.get("context"), Mapping) else {}
        observability = (
            dict(value.get("observability") or {})
            if isinstance(value.get("observability"), Mapping)
            else {}
        )
        for key, item in value.items():
            if key in known:
                continue
            if key.endswith("_error") or key in {"family_exception", "family_error"}:
                errors[key] = item
            elif key in {
                "query_text",
                "target_scope",
                "evidence_goal",
                "sub_question",
                "comparison_candidate",
                "gap",
                "freshness_requirement",
                "source_names",
                "sub_source_types",
                "include_domains",
                "exclude_domains",
                "owner_user_id",
                "project_scope_id",
                "allowed_visibility_scopes",
                "knowledge_types",
                "topic_tags",
                "source_types",
                "selected_sources",
                "selected_sub_source_types",
                "preferred_tool",
                "candidate_tools",
                "used_query_embedding",
            }:
                context[key] = item
            else:
                observability[key] = item
        return {
            "target_problem": value.get("target_problem"),
            "selected_family": value.get("selected_family"),
            "selected_tool": value.get("selected_tool"),
            "generated_query": value.get("generated_query"),
            "query_focus": value.get("query_focus"),
            "acquisition_status": value.get("acquisition_status"),
            "attempts": value.get("attempts") or [],
            "returned_refs": value.get("returned_refs") or [],
            "errors": errors,
            "context": context,
            "observability": observability,
        }

    def get(self, key: str, default: Any = None) -> Any:
        if hasattr(self, key):
            return getattr(self, key)
        if key in self.context:
            return self.context[key]
        if key in self.errors:
            return self.errors[key]
        return self.observability.get(key, default)

    def __getitem__(self, key: str) -> Any:
        value = self.get(key, None)
        if (
            value is None
            and key not in self.context
            and key not in self.errors
            and key not in self.observability
            and not hasattr(self, key)
        ):
            raise KeyError(key)
        return value

    def __iter__(self):
        yield from self.to_legacy_dict().items()

    def to_legacy_dict(self) -> dict[str, Any]:
        data = {
            "target_problem": self.target_problem,
            "selected_family": self.selected_family,
            "selected_tool": self.selected_tool,
            "generated_query": self.generated_query,
            "query_focus": self.query_focus,
            "acquisition_status": self.acquisition_status,
            "attempts": [attempt.to_legacy_dict() for attempt in self.attempts],
            "returned_refs": self.returned_refs,
        }
        data.update(self.context)
        data.update(self.errors)
        data.update(self.observability)
        return data
