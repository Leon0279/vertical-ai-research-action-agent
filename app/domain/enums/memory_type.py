"""Long-term memory category enums."""

from enum import StrEnum


class MemoryType(StrEnum):
    """Memory categories aligned with HLD memory architecture."""

    PROJECT_PROFILE = "PROJECT_PROFILE"
    RESEARCH_KNOWLEDGE = "RESEARCH_KNOWLEDGE"
    DECISION = "DECISION"
    ACTION_EXECUTION = "ACTION_EXECUTION"
    PREFERENCE = "PREFERENCE"
    RESEARCH_POLICY = "RESEARCH_POLICY"
    TRACKING_WATCHLIST = "TRACKING_WATCHLIST"
