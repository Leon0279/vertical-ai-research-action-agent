"""Research evidence coverage 状态枚举。"""

from enum import StrEnum


class ResearchCoverageStatus(StrEnum):
    """表示现有证据对一个受控研究目标的覆盖程度。"""

    # 已覆盖：核心问题和关键方面均已有足够证据支撑。
    COVERED = "covered"

    # 部分覆盖：已有实质证据，但仍存在重要未覆盖方面。
    PARTIALLY_COVERED = "partially_covered"

    # 未覆盖：尚无足以直接支持该研究目标的有效证据。
    NOT_COVERED = "not_covered"
