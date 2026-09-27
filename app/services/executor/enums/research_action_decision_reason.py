"""Research action 选择原因枚举。"""

from enum import StrEnum


class ResearchActionDecisionReason(StrEnum):
    """表示确定性 action selection 规则最终采用的原因码。"""

    # iteration 预算已经耗尽，因此不能再发起新的材料获取。
    ITERATION_BUDGET_EXHAUSTED = "iteration_budget_exhausted"

    # assessment 未识别出仍可通过材料获取推进的有效缺口。
    NO_ACTIONABLE_GAP = "no_actionable_gap"

    # findings 已稳定且证据支撑充分，无需继续获取材料。
    STABLE_WITH_STRONG_SUPPORT = "stable_with_strong_support"

    # runtime 没有声明任何可用于 acquisition 的 retrieval family。
    NO_AVAILABLE_FAMILY = "no_available_family"

    # 延迟预算不足，且当前缺口不值得突破预算继续获取材料。
    LATENCY_CONSTRAINED = "latency_constrained"

    # 当前 coverage target 的兼容获取路径都已被历史判定为低价值。
    ACQUISITION_PATHS_EXHAUSTED = "acquisition_paths_exhausted"

    # evidence 必须新鲜或现有信息已过期，因此必须选择外部路径。
    FRESH_OR_STALE_REQUIRES_EXTERNAL = "fresh_or_stale_requires_external"

    # memory 和 external 都可用时，按默认低成本策略优先选择 memory。
    MEMORY_PREFERRED_BY_DEFAULT = "memory_preferred_by_default"

    # 只有 memory 路径满足当前 evidence need 的资格条件。
    MEMORY_ONLY_CANDIDATE = "memory_only_candidate"

    # memory 因近期低价值历史被排除，因此切换到仍可用的 external 路径。
    MEMORY_BLOCKED_BY_HISTORY = "memory_blocked_by_history"

    # 只有 external 路径满足当前 evidence need 的资格条件。
    EXTERNAL_ONLY_CANDIDATE = "external_only_candidate"

    # 没有任何 acquisition 路径通过规则 gate，只能基于现有状态 refine。
    NO_ELIGIBLE_ACQUISITION_PATH = "no_eligible_acquisition_path"
