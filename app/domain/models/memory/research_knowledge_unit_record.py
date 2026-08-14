"""Domain model for one research_knowledge_units row."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domain.models.source import SourceReference


class ResearchKnowledgeUnitRecord(BaseModel):
    """Typed research knowledge unit aligned with the LLD storage schema."""

    model_config = ConfigDict(extra="forbid")

    knowledge_id: str = Field(
        min_length=1,
        description="必填字段。一条可复用 research knowledge unit 的主标识，用于查询、更新和 canonical 关联。",
    )
    owner_user_id: str = Field(
        min_length=1,
        description="必填字段。隔离 research knowledge record 的用户归属边界。",
    )
    project_scope_id: str | None = Field(
        default=None,
        description="可选字段。项目特定 knowledge recall 使用的项目范围标识；非项目知识时为 None。",
    )
    visibility_scope: str = Field(
        min_length=1,
        description="必填字段。声明的可见性范围，例如 user、project、domain 或 global。",
    )
    visibility_scope_effective: str = Field(
        min_length=1,
        description="必填字段。读取路径实际用于过滤的有效可见性范围。",
    )
    title: str = Field(
        min_length=1,
        description="必填字段。该 knowledge unit 的简短标题，便于展示、筛选和 embedding 构造。",
    )
    summary: str = Field(
        min_length=1,
        description="必填字段。可复用的摘要级 research knowledge，不是原始来源正文。",
    )
    knowledge_type: str = Field(
        min_length=1,
        description=(
            "必填字段。knowledge 分类，例如 concept、method、comparison、conclusion、tradeoff 或 pattern。"
        ),
    )
    topic_tags: list[str] = Field(
        default_factory=list,
        description="可选字段，默认空列表。语义 recall 前用于 metadata 过滤的 topic tag。",
    )
    confidence: float | None = Field(
        default=None,
        description="可选字段。该 knowledge unit 内容的可信度数值；未评估时为 None。",
    )
    source_refs: list[SourceReference] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表。支撑该 research knowledge unit 的 evidence-level "
            "provenance，每个元素必须是 SourceReference。这里的 SourceReference 表示 "
            "knowledge distill 前的原始来源，例如网页、论文、docs 页面、会话或 run output，"
            "而不是 knowledge unit 本身；不要用 knowledge_id、knowledge title、owner_user_id "
            "或 created_by 伪造成 source reference。该字段当前仍以内嵌 JSONB/JSON array "
            "形式落库，由 PostgresResearchKnowledgeMemoryStore 在存储边界负责序列化和反序列化。"
        ),
    )
    source_type: str | None = Field(
        default=None,
        description="可选字段。主要原始来源类型，例如 paper、web_page、user_upload、conversation 或 run_output。",
    )
    derived_from_session_id: str | None = Field(
        default=None,
        description="可选字段。提炼该 knowledge unit 的来源 session 标识；无 session 来源时为 None。",
    )
    derived_from_run_id: str | None = Field(
        default=None,
        description="可选字段。提炼该 knowledge unit 的来源 run 标识；无 run 来源时为 None。",
    )
    created_by: str | None = Field(
        default=None,
        description="可选字段。创建者标签，例如 system、user 或 llm；未知时为 None。",
    )
    status: str = Field(
        min_length=1,
        description="必填字段。knowledge 的生命周期状态，例如 active、superseded、archived 或 pruned。",
    )
    created_at: datetime | None = Field(
        default=None,
        description="可选字段。该 knowledge unit 的首次创建时间。",
    )
    updated_at: datetime | None = Field(
        default=None,
        description="可选字段。该 knowledge unit 的最近更新时间。",
    )
    archived_at: datetime | None = Field(
        default=None,
        description="可选字段。该 knowledge unit 被归档的时间；未归档时为 None。",
    )
    pruned_at: datetime | None = Field(
        default=None,
        description="可选字段。该 knowledge unit 被清理或裁剪的时间；未裁剪时为 None。",
    )
    freshness_sensitivity: str | None = Field(
        default=None,
        description="可选字段。该 knowledge 变得过期的敏感度，例如 low、medium 或 high。",
    )
    freshness_status: str | None = Field(
        default=None,
        description="可选字段。当前新鲜度状态，例如 fresh、aging 或 stale。",
    )
    last_verified_at: datetime | None = Field(
        default=None,
        description="可选字段。该 knowledge 最近一次依据 evidence 验证的时间。",
    )
    freshness_checked_at: datetime | None = Field(
        default=None,
        description="可选字段。该 knowledge 最近一次接受 freshness 评估的时间。",
    )
    staleness_reason: str | None = Field(
        default=None,
        description="可选字段。新鲜度被降级的原因；未降级时为 None。",
    )
    dedupe_key: str | None = Field(
        default=None,
        description="可选字段。用于识别近似重复 knowledge unit 的归一化 key。",
    )
    canonical_knowledge_id: str | None = Field(
        default=None,
        description="可选字段。当前 record 所属 canonical knowledge 的标识。",
    )
    is_canonical: bool = Field(
        default=True,
        description="该 record 是否为 recall 应优先使用的 canonical knowledge unit；默认 True。",
    )
    merged_into_id: str | None = Field(
        default=None,
        description="可选字段。当前 unit 合并到另一条 knowledge 后的目标 knowledge_id；未合并时为 None。",
    )
    embedding_text: str | None = Field(
        default=None,
        description="可选字段。生成 embedding 的文本，通常由 title 与 summary 组合。",
    )
    embedding_vector: list[float] | None = Field(
        default=None,
        description="可选字段。pgvector 语义 recall 使用的 embedding 向量。",
    )
    embedding_model: str | None = Field(
        default=None,
        description="可选字段。生成该向量表示所使用的 embedding 模型名称。",
    )
    embedding_version: str | None = Field(
        default=None,
        description="可选字段。embedding 模型或生成配置的版本标识。",
    )
