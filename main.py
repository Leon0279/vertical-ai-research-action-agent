"""Local application entrypoint."""

from app.common.observability import configure_file_logging

configure_file_logging()

from app.api.app import app

__all__ = ["app"]
