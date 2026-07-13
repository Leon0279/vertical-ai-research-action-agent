"""当前 request run 的运行时能力与执行边界模型。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class RuntimeContext(BaseModel):
    """当前 run 的运行时身份、能力、预算与环境标记。

    RuntimeContext 不表达任务语义，也不承载 evidence 或 conclusion。它用于告诉各 stage：
    当前 run 属于哪个用户/会话、已经走过哪些 stage、可用哪些工具，以及执行预算和环境约束是什么。
    """

    request_id: str = Field(
        min_length=1,
        description=(
            "必填字段，不能为空字符串。当前 request run 的唯一标识。当前项目中有用：RequestIntakeService "
            "会初始化该字段；ResponseAssembler 会把它作为 StructuredOutput.trace_id；日志、trace、memory candidate "
            "和后续排查也可用它关联同一次运行。"
        ),
    )
    user_id: str = Field(
        min_length=1,
        description=(
            "必填字段，不能为空字符串。当前执行上下文的用户归属边界。当前项目中有用：memory loader、research knowledge recall、"
            "ResearchExecutor 和 memory persistence 都应通过该字段做用户隔离。它不是 source author，也不是 publisher。"
        ),
    )
    session_id: str = Field(
        min_length=1,
        description=(
            "必填字段，不能为空字符串。当前 run 所属的 session/thread 边界。当前项目中有用：SessionMemoryStore、"
            "SessionContinuityManager 和 ContextMemoryLoader 通过它连接短期 session continuity。"
        ),
    )
    session_id_generated: bool = Field(
        default=False,
        description=(
            "可选字段，默认 False。表示 session_id 是否由系统自动生成，而不是由调用方显式提供。当前项目中有用："
            "ResponseAssembler 会把该信息放入 output metadata，便于调用方理解 session continuity 是否来自系统兜底。"
        ),
    )
    stage_history: list[str] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表。当前 run 已经过的 workflow stage 名称顺序。当前项目中有用："
            "ResearchActionPipeline 会在每个 stage 前追加 stage name，ResponseAssembler 会把它输出，测试也会用它验证固定 workflow 顺序。"
            "该字段只记录 stage 名称，不记录每个 stage 的完整输入输出。"
        ),
    )

    available_tools: list[str] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表。当前 run 可用 tool/capability 的轻量列表。当前项目中有用但默认可能为空："
            "后续 ResearchExecutor 或 stage input projection 可读取它约束工具使用。列表元素应是工具或能力标识字符串，"
            "不是完整 tool config。"
        ),
    )
    tool_registry_version: str | None = Field(
        default=None,
        description=(
            "可选字段。当前 active tool registry 的版本标识。当前项目中暂未稳定使用，但对未来 tool capability "
            "排查和复现实验有用。没有版本信息时为 None。"
        ),
    )
    latency_budget_ms: int | None = Field(
        default=None,
        description=(
            "可选字段。当前 run 的延迟预算，单位毫秒。当前项目中有用：ResearchExecutor 会把正数值透传为 "
            "ToolExecutionLayerRequest.timeout_limit_ms，用于约束 retrieval/recovery。None 表示未指定总延迟预算。"
        ),
    )
    iteration_budget: int | None = Field(
        default=None,
        description=(
            "可选字段。当前 run 允许消耗的 reasoning / research iteration 上限。当前项目中有用："
            "ResearchExecutorService 会优先使用该字段控制 research loop 轮数；未设置时退回 ExecutionGuardrails.max_iterations。"
            "该字段约束迭代次数，不表示 tool 内部 retry_budget。"
        ),
    )
    scope_restrictions: list[str] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表。当前 run 的访问或行动范围限制。当前项目中有用但当前执行逻辑较轻："
            "未来 stage input projection、memory recall、tool execution 或 action generation 可读取它避免越界。"
            "列表项应是简短 scope restriction 描述或标识。"
        ),
    )
    environment_flags: list[str] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表。影响当前 run 行为的环境标记。当前项目中有用但当前多数路径暂不读取："
            "可用于表达测试模式、只读模式、禁用外部网络、启用实验能力等运行时开关。列表项应是稳定 flag 字符串。"
        ),
    )
