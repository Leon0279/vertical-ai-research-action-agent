"""Research evidence 支撑强度枚举。"""

from enum import StrEnum


class ResearchSupportStrength(StrEnum):
    """表示现有证据对当前研究判断的整体支撑强度。"""

    # 支撑已经足够强，可以据此形成稳定判断并考虑停止研究。
    STRONG_ENOUGH = "strong_enough"

    # 已有明确且实质的支撑，但距离稳定结论仍需补强。
    MODERATE_SUPPORT = "moderate_support"

    # 只有少量、间接或质量较低的信号，结论仍容易变化。
    WEAK_SUPPORT = "weak_support"

    # 现有材料之间存在实质矛盾，无法汇聚为单一稳定判断。
    CONFLICTING_SUPPORT = "conflicting_support"

    # 尚无足以支撑当前判断的有效材料。
    INSUFFICIENT_SUPPORT = "insufficient_support"
