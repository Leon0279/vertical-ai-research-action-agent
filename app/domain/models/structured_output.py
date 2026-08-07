"""最终 orchestration 返回给调用方的结构化输出模型。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.domain.enums.task_type import TaskType
from app.domain.enums.workflow_pattern import WorkflowPattern
from app.domain.models.action_item import ActionItem
from app.domain.models.citation import Citation


class StructuredOutput(BaseModel):
    """最终面向用户和上层 API 的结构化响应。

    `answer` 是用户真正阅读的完整正文；其它字段用于摘要展示、来源核验、行动项提取、
    置信度表达和运行诊断，不应通过简单拼接替代 `answer`。
    """

    trace_id: str | None = Field(
        default=None,
        description=(
            "可选字段。当前 run 的 trace/request id。当前项目中有用：ResponseAssemblerService "
            "会从 RuntimeContext.request_id 写入，用于日志关联、问题排查和前端请求追踪。"
        ),
    )
    task_type: TaskType = Field(
        description=(
            "必填字段。当前请求被解释出的任务类型。当前项目中有用：ResponseAssemblerService "
            "会从 RunningState.task_type 转换得到；调用方可据此选择展示模板，例如 comparison、recommendation、"
            "action_planning 或 tracking。"
        ),
    )
    workflow_pattern: WorkflowPattern = Field(
        description=(
            "必填字段。当前 run 实际采用的 workflow pattern。当前项目中有用：ResponseAssemblerService "
            "优先使用 RunningState.workflow_pattern，否则根据 task_type fallback；上层可用它理解本次回答经过了哪类 workflow。"
        ),
    )
    answer: str = Field(
        min_length=1,
        description=(
            "必填字段。最终给用户阅读的完整自然语言答案。当前项目中有用：ConclusionGeneratorService "
            "写入 RunningState.final_answer，ResponseAssemblerService 再映射到该字段。它不是 summary、recommendation、"
            "action_items 的机械拼接，而是基于当前 research state 生成的一段完整回答。"
        ),
    )
    summary: str = Field(
        min_length=1,
        description=(
            "必填字段。最终答案的简短摘要、TL;DR 或预览文案。当前项目中有用：ResponseAssemblerService "
            "优先使用 RunningState.final_summary；如果缺失，会从 final_answer 派生安全 fallback。它不承担完整回答职责。"
        ),
    )
    recommendation: str | None = Field(
        default=None,
        description=(
            "可选字段。结构化主推荐、主判断或主结论短句。当前项目中有用：Recommendation、Decision、"
            "Action Planning 类任务可用它快速展示核心建议；MemoryDistillerService 也会消费 RunningState.final_recommendation。"
            "纯信息型回答可以为空。"
        ),
    )
    action_items: list[ActionItem] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表。结构化行动项。当前项目中有用：ResponseAssemblerService 会从 "
            "RunningState.action_items 转换得到；前端、任务系统或未来 action memory 可直接消费。没有明确下一步行动时为空。"
        ),
    )
    citations: list[Citation] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表。最终答案引用的轻量来源列表。当前项目中有用：ConclusionGeneratorService "
            "会基于 RunningState.retrieved_evidence_refs 生成并过滤 citation，ResponseAssemblerService 原样输出；"
            "用户可用它核验答案依据。"
        ),
    )
    confidence: float | None = Field(
        default=None,
        description=(
            "可选字段。最终答案整体置信度分数。当前项目中有用：ResponseAssemblerService 会把 "
            "RunningState.confidence 的 low/medium/high 标签映射为 0.2/0.5/0.8；如果没有置信度信号则为 None。"
        ),
    )
    caveats: list[str] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表。最终答案的限制、风险、未覆盖范围或仍未解决的问题。当前项目中有用："
            "ConclusionGeneratorService 会把 open questions 和 evidence 不足转成用户可读 caveats，ResponseAssemblerService "
            "原样输出，帮助用户避免过度信任答案。"
        ),
    )
    stage_history: list[str] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表。当前 run 实际执行过的 pipeline stage 名称。当前项目中有用："
            "ResponseAssemblerService 会从 RuntimeContext.stage_history 写入，用于调试、观测和测试 stage order。"
        ),
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "可选字段，默认空 dict。最终输出的非核心运行 metadata。当前项目中包含 session_id 和 "
            "session_id_generated；未来可加入轻量 routing/debug 信息。不要把完整 prompt、raw tool payload、"
            "完整 evidence 正文或敏感 provider response 放在这里。"
        ),
    )
