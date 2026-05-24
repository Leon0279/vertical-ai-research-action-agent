"""Domain model for citations."""

from pydantic import BaseModel


class Citation(BaseModel):
    """Citation payload for user-facing traceability."""

    source: str
    note: str | None = None

