"""Research gap 性质枚举。"""

from enum import StrEnum


class ResearchGapNature(StrEnum):
    """表示研究缺口为什么阻碍当前判断继续推进。"""

    # 缺失：当前没有该问题或方面所需的证据。
    MISSING = "missing"

    # 薄弱：已有相关材料，但质量、数量或直接性不足。
    WEAK = "weak"

    # 模糊：现有材料含义不清，无法确定应如何解释。
    AMBIGUOUS = "ambiguous"

    # 冲突：不同材料对同一关键事实或判断给出不一致结论。
    CONFLICTING = "conflicting"

    # 失衡：比较任务中不同候选项或维度的证据覆盖不对称。
    IMBALANCED = "imbalanced"

    # 过期：现有材料可能已经不能代表当前状态，需要更新证据。
    STALE = "stale"

    # 不可行动：信息存在，但仍不足以支持明确决策或下一步行动。
    NOT_ACTIONABLE = "not_actionable"

    # 无缺口：当前没有需要继续获取材料处理的研究缺口。
    NONE = "none"
