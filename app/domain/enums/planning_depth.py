"""Planning-depth enums used by decomposition."""

from enum import StrEnum


class PlanningDepth(StrEnum):
    """定义规划深度的可选枚举值。

Represents how deeply the system should plan before execution."""

    NONE = "NONE"
    SHALLOW = "SHALLOW"
    MEDIUM = "MEDIUM"
    DEEP = "DEEP"
