"""Research evidence need 目的枚举。"""

from enum import StrEnum


class ResearchNeedPurpose(StrEnum):
    """表示下一项证据需要解决的具体研究目的。"""

    # 为尚未覆盖的目标建立第一层直接证据覆盖。
    ESTABLISH_COVERAGE = "establish_coverage"

    # 在已有相关材料的基础上提高证据强度和可靠性。
    STRENGTHEN_SUPPORT = "strengthen_support"

    # 获取能够澄清术语、边界或现有材料含义的证据。
    RESOLVE_AMBIGUITY = "resolve_ambiguity"

    # 获取能够判断矛盾材料哪一方更可信或解释冲突来源的证据。
    RESOLVE_CONFLICT = "resolve_conflict"

    # 补足 comparison 中证据较少的候选项或维度，使比较恢复平衡。
    REBALANCE_COMPARISON = "rebalance_comparison"

    # 用更新材料替换可能已经过期的状态信息。
    REFRESH_STATUS = "refresh_status"

    # 补充可支持明确推荐、决策或行动步骤的证据。
    IMPROVE_ACTIONABILITY = "improve_actionability"

    # 当前没有需要通过新增证据完成的研究目的。
    NONE = "none"
