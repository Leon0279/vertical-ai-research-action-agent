"""Family Selection Service 的输入模型。"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.domain.enums import ActionMode, FamilyName
from app.domain.models.tool_execution_layer.evidence_shape import EvidenceShape


class FamilySelectionRequest(BaseModel):
    """选择 retrieval family 时使用的标准化输入。

    该模型是 Tool Execution Layer 中 family selection 子服务的公开输入边界。它只负责
    表达“当前 retrieval intent 应该从哪个 family 获取信息”，不包含 selected_tool，
    也不包含具体 family/tool 的执行参数。当前项目中该模型有用：ToolExecutionLayerService
    会从 Research Executor 投影过来的 ToolExecutionLayerRequest 中构造它；FamilySelectionService
    会基于这些字段做 deterministic family ranking，输出 selected_family 供后续 query generation
    和 family execution 使用。
    """

    target_problem: str = Field(
        description=(
            "必填字段。当前这次 retrieval 需要解决的目标问题或证据缺口。当前项目中有用："
            "FamilySelectionService 会先 trim 该字段，并在为空时返回 selection_status='failed'；"
            "它也是 selection_trace 中保留的核心输入。该字段应是 Research Executor 已经聚焦后的检索目标，"
            "不是最终回答文本，也不是完整 ExecutionContext。"
        ),
    )
    action_mode: ActionMode = Field(
        default=ActionMode.EXTERNAL_ACQUISITION,
        description=(
            "可选字段，默认 ActionMode.EXTERNAL_ACQUISITION。高层信息获取模式，用来形成 family selection 的初始候选范围。"
            "当前项目中有用：memory_backed_acquisition 会把初始范围限制为 research_knowledge_recall；"
            "external_acquisition 会把初始范围限制为 docs_search、paper_search、web_search；any 会允许四个 supported family "
            "全部进入初始范围。该字段是我们创建的 ActionMode 枚举类型，使用 StrEnum，旧字符串输入仍可兼容，"
            "JSON 输出仍是 external_acquisition / memory_backed_acquisition / any 这样的字符串值。"
        ),
    )
    evidence_goal: str | None = Field(
        default=None,
        description=(
            "可选字段。描述本轮检索希望达成的证据目标，例如 establish_coverage、improve_actionability、"
            "rebalance_comparison、resolve_conflict、refresh_status、strengthen_support、resolve_ambiguity。"
            "当前项目中有用：FamilySelectionService 会根据该字段给不同 family 加权，例如 refresh_status 偏向 web_search，"
            "rebalance_comparison / resolve_conflict 偏向 paper_search；RetrievalQueryGenerationService 也会继续使用同类语义生成 query。"
            "该字段不是 enum，当前保持字符串是为了允许上游 planner / Research Executor 逐步扩展 evidence goal。"
        ),
    )
    evidence_shape: EvidenceShape | None = Field(
        default=None,
        description=(
            "可选字段。期望获取的证据形态，类型为 EvidenceShape。当前项目中有用：FamilySelectionService 会读取 "
            "desired_evidence_kind、freshness_requirement、breadth 来给 family 加权；例如 status_evidence 和 fresh_required "
            "会提升 web_search，comparison_evidence 会提升 paper_search，narrow 会提升 docs_search。该对象已有独立中文字段注释；"
            "本字段为空时，family selection 会只依赖 action_mode、evidence_goal、task_framing、evidence_strategy 和 family 约束。"
        ),
    )
    task_type: str | None = Field(
        default=None,
        description=(
            "可选字段。上游 planning / routing 对任务类型的解释结果。当前项目中保守保留但 FamilySelectionService v1 "
            "暂不直接使用该字段进行打分；它会被 trim 后保留在 selection_trace 中，方便后续观察上游语义投影是否合理。"
            "该字段不是 Tool Execution Layer 的核心输入，后续如果长期没有真实消费方，可以再考虑从 family selection request 中下沉或删除。"
        ),
    )
    task_framing: str | None = Field(
        default=None,
        description=(
            "可选字段。上游对当前 retrieval task 的轻量 framing，例如“复用已有知识”“需要最新状态”“比较不同方法”等。"
            "当前项目中有用：FamilySelectionService 会把它和 evidence_strategy 拼接后做关键词打分，memory/recall/reuse 会提升 "
            "research_knowledge_recall，comparison/method/research 会提升 paper_search，latest/fresh/current/status 会提升 web_search。"
            "该字段也会进入 selection_trace，用于解释为什么某个 family 被提升。"
        ),
    )
    evidence_strategy: str | None = Field(
        default=None,
        description=(
            "可选字段。上游 workflow/router/planner 给出的证据获取策略文本。当前项目中有用：FamilySelectionService 会和 "
            "task_framing 一起做上下文关键词打分，用于轻量影响 family ranking。它不是 evidence sufficiency 判断，也不驱动 tool execution；"
            "只作为 family selection 的弱信号和 selection_trace 的可观测输入。"
        ),
    )
    allowed_source_families: list[FamilyName] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表。允许参与本次选择的 retrieval family 白名单。当前项目中有用：FamilySelectionService 会在 "
            "action_mode 初始范围和 available_families 过滤之后，再用该字段做 allow-list 过滤；为空表示不额外限制。"
            "元素类型为 FamilyName，当前可选值包括 research_knowledge_recall、docs_search、paper_search、web_search；"
            "旧字符串输入仍可由 Pydantic 兼容转换为 FamilyName。该字段表达强约束，不是偏好。"
        ),
    )
    preferred_source_families: list[FamilyName] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表。上游希望优先考虑的 retrieval family 列表。当前项目中有用：FamilySelectionService 会对列表中仍在候选集内的 "
            "family 增加强偏好分；但 preferred 不会绕过 action_mode、available_families、allowed_source_families 或 blocked_source_families。"
            "也就是说，它只影响排序，不强制选择。元素类型为 FamilyName，JSON 输出仍是字符串数组。"
        ),
    )
    blocked_source_families: list[FamilyName] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表。本次 family selection 必须排除的 retrieval family。当前项目中有用：FamilySelectionService 会在 "
            "available / allowed 过滤之后移除这些 family；ToolExecutionLayerService 在 fallback_to_broader_search 时也会把刚尝试过的 "
            "family 加入 blocked family 集合，避免立刻选回同一个 family。元素类型为 FamilyName，表示强约束。"
        ),
    )
    available_families: list[FamilyName] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表。当前运行时实际可用的 retrieval family 列表。当前项目中有用：ToolExecutionLayerService 会先根据已注入的 "
            "family services 计算 effective_available_families，再传给 FamilySelectionService；FamilySelectionService 会只保留 "
            "action_mode 初始范围中同时出现在 available_families 里的 family。为空表示 family selection 不按 runtime availability "
            "额外过滤，但仍受 action_mode、allowed_source_families、blocked_source_families 影响。元素类型为 FamilyName。"
        ),
    )
