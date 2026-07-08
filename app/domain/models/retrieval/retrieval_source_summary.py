"""retrieval 输出中的来源摘要模型。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, Field, model_validator

from app.domain.enums import FamilyName


class RetrievalSourceSummary(BaseModel):
    """tool、family 和 Tool Execution Layer 共用的来源/provenance 摘要。

    该模型只表达稳定的来源摘要，不承载完整 provider raw payload。当前项目中它会出现在
    tool result、family result、ToolExecutionLayerResult 和 EvidenceProcessingRequest 中。
    """

    selected_family: FamilyName | None = Field(
        default=None,
        description=(
            "可选字段。当前执行选择的 retrieval family。当前项目中该字段有用：tool 层通常会写入自己的 family，"
            "例如 docs_search、paper_search、web_search、research_knowledge_recall；family / TEL 会继续保留或覆盖该值，"
            "EvidenceProcessingService 可通过 source_summary 或 retrieval_trace 读取它作为 provenance fallback。"
        ),
    )
    selected_tool: str | None = Field(
        default=None,
        description=(
            "可选字段。family 内部实际执行的 tool 名称。当前项目中该字段有用：虽然 ToolExecutionLayerService 顶层不负责 "
            "selected_tool，但 family/tool 结果会保留该字段作为 provenance。docs tool 当前写入 llms_txt_docs_search_v1；"
            "paper/web/memory tool 分别写入各自 tool id。EvidenceProcessingService 会把它写入 ProcessedEvidenceUnit.metadata['selected_tool']。"
        ),
    )
    normalized_count: int = Field(
        default=0,
        ge=0,
        description=(
            "可选字段，默认 0，必须大于等于 0。当前结果中归一化候选材料的数量。当前项目中该字段有用："
            "tool/family/TEL 都会用它表达本层最终对外暴露的 normalized_items 数量；它也用于调试 no_result、partial_success "
            "和 recovery 相关路径。"
        ),
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "可选字段，默认空 dict。来源摘要中的扩展信息，当前项目中有用，但不属于稳定主字段。"
            "docs_search adapter/tool 当前会写入 searched_sub_source_types，表示本次实际搜索过的 docs 子来源类型；"
            "其它 tool/family 可放 provider-specific source coverage、searched domains、selected sources 等摘要。"
            "兼容旧 dict 输入时，除 selected_family、selected_tool、normalized_count、metadata 之外的 key 会被收拢到这里。"
        ),
    )

    @model_validator(mode="before")
    @classmethod
    def _from_legacy_mapping(cls, value: Any) -> Any:
        if isinstance(value, cls) or not isinstance(value, Mapping):
            return value
        metadata = dict(value.get("metadata") or {}) if isinstance(value.get("metadata"), Mapping) else {}
        known = {"selected_family", "selected_tool", "normalized_count", "metadata"}
        for key, item in value.items():
            if key not in known:
                metadata[key] = item
        return {
            "selected_family": value.get("selected_family"),
            "selected_tool": value.get("selected_tool"),
            "normalized_count": value.get("normalized_count") or 0,
            "metadata": metadata,
        }

    def get(self, key: str, default: Any = None) -> Any:
        if hasattr(self, key):
            return getattr(self, key)
        return self.metadata.get(key, default)

    def __getitem__(self, key: str) -> Any:
        value = self.get(key, None)
        if value is None and key not in self.metadata and not hasattr(self, key):
            raise KeyError(key)
        return value

    def __iter__(self):
        yield from self.to_legacy_dict().items()

    def to_legacy_dict(self) -> dict[str, Any]:
        data = {
            "selected_family": self.selected_family,
            "selected_tool": self.selected_tool,
            "normalized_count": self.normalized_count,
        }
        data.update(self.metadata)
        return data
