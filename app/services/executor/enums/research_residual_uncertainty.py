"""Research 剩余不确定性枚举。"""

from enum import StrEnum


class ResearchResidualUncertainty(StrEnum):
    """表示单轮研究结束后仍未解决的不确定性水平。"""

    # 高：关键缺口仍然阻碍可靠结论，继续研究通常具有明显价值。
    HIGH = "high"

    # 中：已有实质判断，但仍存在可能影响结论或建议的重要边界。
    MODERATE = "moderate"

    # 低：仅剩次要不确定性，通常可以形成可靠的阶段结论。
    LOW = "low"

    # 极小：核心问题已经充分解决，继续研究的边际价值很低。
    MINIMAL = "minimal"
