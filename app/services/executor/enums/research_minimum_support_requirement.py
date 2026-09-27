"""Research 最低支撑要求枚举。"""

from enum import StrEnum


class ResearchMinimumSupportRequirement(StrEnum):
    """表示将当前缺口视为已推进所需达到的最低证据强度。"""

    # 任意明确相关的新信号即可视为取得初步推进。
    ANY_RELEVANT_SIGNAL = "any_relevant_signal"

    # 至少需要形成实质但未必最终稳定的中等支撑。
    MODERATE_SUPPORT = "moderate_support"

    # 必须获得足以形成稳定结论的强支撑。
    STRONG_SUPPORT = "strong_support"

    # 当前没有需要满足的新增证据门槛。
    NONE = "none"
