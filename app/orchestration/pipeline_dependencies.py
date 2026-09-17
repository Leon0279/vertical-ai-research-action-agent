"""Typed dependency aggregate for orchestration pipeline."""

from __future__ import annotations

from dataclasses import dataclass

from app.services.executor.contracts.research_executor_protocol import (
    ResearchExecutorProtocol,
)
from app.services.intake.contracts.request_intake_protocol import RequestIntakeProtocol
from app.services.memory.contracts.context_memory_loader_protocol import (
    ContextMemoryLoaderProtocol,
)
from app.services.memory.contracts.memory_distiller_protocol import (
    MemoryDistillerProtocol,
)
from app.services.memory.contracts.memory_persistence_protocol import (
    MemoryPersistenceProtocol,
)
from app.services.memory.contracts.session_continuity_manager_protocol import (
    SessionContinuityManagerProtocol,
)
from app.services.output.contracts.conclusion_generator_protocol import (
    ConclusionGeneratorProtocol,
)
from app.services.output.contracts.response_assembler_protocol import (
    ResponseAssemblerProtocol,
)
from app.services.planner.contracts.decomposition_planner_protocol import (
    DecompositionPlannerProtocol,
)
from app.services.planner.contracts.task_interpreter_protocol import (
    TaskInterpreterProtocol,
)
from app.services.planner.contracts.workflow_router_protocol import WorkflowRouterProtocol


@dataclass(slots=True)
class PipelineDependencies:
    """承载研究行动管线所需的 APP-scoped service contracts。"""

    # 初始化 ExecutionContext 的请求入口 service。
    request_intake: RequestIntakeProtocol
    # 解析用户目标、任务类型和约束的任务理解 service。
    task_interpreter: TaskInterpreterProtocol
    # 选择当前请求 workflow pattern 的路由 service。
    workflow_router: WorkflowRouterProtocol
    # 生成计划、子问题与初始 evidence guidance 的规划 service。
    decomposition_planner: DecompositionPlannerProtocol
    # 读取 session 和长期 memory 并填充 supplemental context 的 service。
    context_memory_loader: ContextMemoryLoaderProtocol
    # 驱动 evidence-driven research loop 的研究执行 service。
    research_executor: ResearchExecutorProtocol
    # 基于 research state 生成最终用户可读结论的 service。
    conclusion_generator: ConclusionGeneratorProtocol
    # 从当前 run 稳定输出中提取长期 memory candidate 的 service。
    memory_distiller: MemoryDistillerProtocol
    # 将 memory candidate 写入 typed durable store 的持久化 service。
    memory_persistence: MemoryPersistenceProtocol
    # 滚动更新短期 session continuity memory 的 service。
    session_continuity_manager: SessionContinuityManagerProtocol
    # 将 ExecutionContext 映射为 API 层 StructuredOutput 的输出组装 service。
    response_assembler: ResponseAssemblerProtocol
