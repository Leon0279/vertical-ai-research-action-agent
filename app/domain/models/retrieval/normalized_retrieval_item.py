"""retrieval tool 返回的标准化候选材料模型。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.domain.models.source import SourceReference


class NormalizedRetrievalItem(BaseModel):
    """当前项目 retrieval 链路中的候选材料主模型。

    该模型由各 tool 产出，经 family service、ToolExecutionLayerService 继续传递，
    最终由 EvidenceProcessingService 消费。它承载“可被加工成 evidence 的材料”，
    不承载最终结论，也不代表已经完成 evidence sufficiency 判断。
    """

    model_config = ConfigDict(extra="forbid")

    item_id: str = Field(
        default="",
        description=(
            "可选字段，默认空字符串。当前 retrieval result 内部的 item 标识。当前项目中该字段有用："
            "EvidenceProcessingService 会用它辅助去重和生成 evidence metadata；tool 层通常会填 docs entry id、"
            "paper id、web result id 或 knowledge id。它只要求在一次 retrieval 输出内相对稳定，不要求全局唯一。"
        ),
    )
    source_family: str = Field(
        default="",
        description=(
            "可选字段，默认空字符串。产出该 item 的 retrieval family，例如 docs_search、paper_search、"
            "web_search、research_knowledge_recall。当前项目中该字段有用：EvidenceProcessingService 会将它写入 "
            "ProcessedEvidenceUnit.source_family，并用于 evidence summary 的 source family coverage。"
        ),
    )
    source_reference: SourceReference = Field(
        description=(
            "必填字段。候选材料对应的正式来源引用。当前项目中该字段有用：它是 normalized item 的 canonical provenance，"
            "已替代旧的 source_type/source_ref 字段；EvidenceProcessingService 会从 source_reference.source_type "
            "派生 ProcessedEvidenceUnit.source_type，并优先从 source_reference.source_url，其次 source_reference.source_id "
            "派生 ProcessedEvidenceUnit.source_ref / support_refs。docs tool 会直接使用 docs_search adapter 返回的 "
            "SourceReference；web/paper/memory tool 会在 tool 层用现有 adapter 或 memory record 字段构造 SourceReference。"
        )
    )
    content: str = Field(
        default="",
        description=(
            "可选字段，默认空字符串。候选材料正文。当前项目中该字段有用：EvidenceProcessingService 会读取该字段做质量过滤、"
            "dedup、LLM structuring 或 deterministic fallback。docs tool 当前填 docs snippet/content；web/paper tool 可能填 "
            "search snippet、summary 或 fetched full content；memory tool 填 reusable knowledge summary。"
        ),
    )
    content_type: str | None = Field(
        default=None,
        description=(
            "可选字段。content 的形态说明。当前项目中该字段有用但不是强控制字段：下游主要用于 provenance 和诊断。"
            "当前常见值包括 text_snippet、document_chunk、knowledge_summary。EvidenceProcessingService 当前不按该字段分支处理，"
            "但会保留它作为 typed item 的一部分，供后续证据处理或调试使用。"
        ),
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "可选字段，默认空 dict。tool/provider-specific 附加信息，当前项目中有用，但它不是稳定主字段。"
            "调用方应优先使用 item_id、source_family、source_reference、content、content_type 等正式字段；metadata "
            "用于承接不同 tool 的差异信息。docs tool 当前会写入：title（docs 页面标题）、sub_source_type（docs 子来源类型）、"
            "url（docs 页面 URL）、section（docs section）、rank（排序位置）、score（adapter 相关性分数），并合并 adapter result metadata，"
            "例如 manifest_summary、page_fetch_error。web tool 可能写入 search_snippet、content_fetch_status、fetched_images、"
            "fetched_favicon 等；paper tool 可能写入 authors、paper_id_type、arxiv_id、categories、content_fetch_status 等；memory tool 可能写入 "
            "knowledge_type、topic_tags、confidence、freshness_status 等。不要把已经稳定建模的主字段长期塞在这里。"
        ),
    )

    def get(self, key: str, default: Any = None) -> Any:
        if hasattr(self, key):
            return getattr(self, key)
        return self.metadata.get(key, default)

    def __getitem__(self, key: str) -> Any:
        value = self.get(key, None)
        if value is None and key not in self.metadata and not hasattr(self, key):
            raise KeyError(key)
        return value

    def __eq__(self, other: object) -> bool:
        if isinstance(other, dict):
            return all(self.get(key) == value for key, value in other.items())
        return super().__eq__(other)
