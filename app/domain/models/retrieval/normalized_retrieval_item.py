"""retrieval tool 返回的标准化候选材料模型。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import FamilyName
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
    source_family: FamilyName | None = Field(
        default=None,
        description=(
            "可选字段，默认 None。产出该 item 的 retrieval family，例如 docs_search、paper_search、"
            "web_search、research_knowledge_recall。当前项目中该字段有用：EvidenceProcessingService 会将它写入 "
            "ProcessedEvidenceUnit.source_family，并用于 evidence summary 的 source family coverage。"
        ),
    )
    source_references: list[SourceReference] = Field(
        min_length=1,
        description=(
            "必填字段，至少包含 1 个 SourceReference。候选材料对应的正式来源引用列表。当前项目中该字段有用："
            "它是 normalized item 的 canonical provenance list，已替代旧的 source_reference、source_type/source_ref 字段。"
            "第一个元素是 primary source reference，用于保持 EvidenceProcessingService 现有去重、source_type 和 source_ref "
            "派生语义稳定；完整列表用于 support_refs 和 provenance。单来源 tool 应传长度为 1 的列表；"
            "research_knowledge_recall 可以把 ResearchKnowledgeUnitRecord.source_refs 中的多个 distill 前原始来源全部传入。"
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
            "调用方应优先使用 item_id、source_family、source_references、content、content_type 等正式字段；metadata "
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
