"""Planning-depth enums used by decomposition."""

from enum import StrEnum


class PlanningDepth(StrEnum):
    """Represents how deeply the system should plan before execution."""

    NONE = "NONE"
    SHALLOW = "SHALLOW"
    MEDIUM = "MEDIUM"
    DEEP = "DEEP"
