"""Task type classification enums."""

from enum import StrEnum


class TaskType(StrEnum):
    """定义任务类型的可选值。

Supported top-level task categories from HLD."""

    TOPIC_EXPLORATION = "TOPIC_EXPLORATION"
    COMPARISON = "COMPARISON"
    RECOMMENDATION = "RECOMMENDATION"
    ACTION_PLANNING = "ACTION_PLANNING"
    TRACKING = "TRACKING"
