"""当前 run 的完整执行上下文模型。"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.domain.models.context.running_state import RunningState
from app.domain.models.context.runtime_context import RuntimeContext
from app.domain.models.context.supplemental_context import SupplementalContext


class ExecutionContext(BaseModel):
    """当前 request run 的完整执行环境。

    ExecutionContext 是顶层 workflow 各 stage 之间共享的上下文边界，由核心可变状态、
    supporting context 和 runtime/capability 信息组成。各 stage 应从该对象投影出自己需要的
    stage input，而不是绕过它私自拼接上下文。
    """

    running_state: RunningState = Field(
        description=(
            "必填字段。当前 run 的核心可变工作状态。当前项目中有用：TaskInterpreter、"
            "WorkflowRouter、Planner、ResearchExecutor、ConclusionGenerator、MemoryDistiller 等 stage "
            "都会读取或更新其中的稳定字段，例如 task_type、plan、evidence_summary、intermediate_findings、"
            "final_recommendation 等。该字段始终存在，不应放入 raw tool payload、完整外部文档或大段 supporting material。"
        ),
    )
    supplemental_context: SupplementalContext = Field(
        default_factory=SupplementalContext,
        description=(
            "可选字段，默认空 SupplementalContext。当前 run 中已被筛选但未吸收到 RunningState 的 supporting context。"
            "当前项目中有用：ContextMemoryLoader 会把 session/project/decision/action/policy/research/external evidence "
            "等支持性摘要放入这里，供 planning、research、conclusion 等 stage 按需消费。它不是核心工作状态，"
            "也不应成为未筛选 raw material 的临时垃圾桶。"
        ),
    )
    runtime_context: RuntimeContext = Field(
        description=(
            "必填字段。当前 run 的运行时身份、能力和预算边界。当前项目中有用：pipeline 用 stage_history 记录阶段顺序，"
            "ResearchExecutor 使用 user_id、iteration_budget、latency_budget_ms 等字段约束 retrieval/evidence loop，"
            "memory 相关 service 使用 user_id/session_id/project scope 共同维护访问边界。该字段描述运行时环境，"
            "不承载任务语义或 evidence 内容。"
        ),
    )
