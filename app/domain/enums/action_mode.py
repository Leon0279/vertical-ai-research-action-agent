"""Tool acquisition action mode enums."""

from enum import StrEnum


class ActionMode(StrEnum):
    """Tool Execution Layer family selection 的 acquisition mode。"""

    MEMORY_BACKED_ACQUISITION = "memory_backed_acquisition"
    EXTERNAL_ACQUISITION = "external_acquisition"
    ANY = "any"
