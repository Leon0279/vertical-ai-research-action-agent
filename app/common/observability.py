"""Structured application logging and request trace context helpers."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from contextvars import ContextVar, Token
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from app.config.env_loader import load_env_file

_TRACE_ID: ContextVar[str | None] = ContextVar("vaa_trace_id", default=None)
_HANDLER_MARKER = "_vaa_json_file_handler"
_DEFAULT_MESSAGE_LIMIT = 2_000
_QUERY_TEXT_LIMIT = 500

_STRUCTURED_FIELDS = (
    "duration_ms",
    "research_status",
    "research_iteration_count",
    "citation_count",
    "attempt_index",
    "selected_family",
    "selected_tool",
    "generated_query",
    "query_fingerprint",
    "acquisition_status",
    "evaluation_status",
    "recovery_action",
    "next_step_hint",
    "retry_count",
    "fallback_applied",
    "execution_status",
    "attempt_count",
    "recovery_attempt_count",
    "recovery_exhausted_reason",
    "error_info",
    "provider_http_status",
    "provider_error_code",
    "provider_request_id",
    "finish_reason",
    "exception_type",
    "provider",
    "operation",
    "configured_timeout_seconds",
    "http_status",
    "error_category",
    "retryable",
    "result_count",
    "download_bytes",
    "response_content_type",
    "extraction_status",
    "paper_id",
    "failure_stage",
    "failure_reason",
    "attempt_error_info",
    "iteration_index",
    "remaining_iteration_budget",
    "remaining_iteration_budget_after_current",
    "candidate_action_modes",
    "action_mode",
    "action_rationale",
    "acquisition_paths_exhausted",
    "top_gap_nature",
    "top_gap_severity",
    "evidence_need_purpose",
    "desired_evidence_kind",
    "freshness_requirement",
    "coverage_target_key",
    "allowed_source_families",
    "preferred_source_families",
    "blocked_source_families",
    "fallback_policy",
    "processed_evidence_count",
    "top_gap_progress",
    "evidence_gain",
    "finding_progress",
    "residual_uncertainty",
    "short_circuit_reason",
    "proposed_iteration_outcome",
    "iteration_outcome",
    "outcome_decision_source",
    "outcome_guardrail_applied",
    "outcome_rationale",
)

_BEARER_PATTERN = re.compile(r"(?i)(\bbearer\s+)[^\s,;]+")
_CREDENTIAL_PATTERN = re.compile(
    r"(?i)(\b(?:api[_-]?key|authorization|cookie|password|client_secret|access_token)"
    r"\b[\"']?\s*[:=]\s*[\"']?)[^\s,;\"']+"
)


@dataclass(frozen=True, slots=True)
class FileLoggingSettings:
    """Runtime settings for the local rotating JSONL application log."""

    enabled: bool
    path: Path
    level: int
    max_bytes: int
    backup_count: int

    @classmethod
    def from_env(cls) -> FileLoggingSettings:
        """Load file logging settings after applying the local ``.env`` file."""

        load_env_file()
        return cls(
            enabled=_boolean_env("APP_LOG_ENABLED", default=True),
            path=_log_path(os.getenv("APP_LOG_PATH", "logs/app.jsonl")),
            level=_log_level(os.getenv("APP_LOG_LEVEL", "INFO")),
            max_bytes=_positive_int_env(
                "APP_LOG_MAX_BYTES",
                default=10 * 1024 * 1024,
            ),
            backup_count=_positive_int_env("APP_LOG_BACKUP_COUNT", default=5),
        )


class JsonLineFormatter(logging.Formatter):
    """Render allow-listed application diagnostics as one JSON object per line."""

    def format(self, record: logging.LogRecord) -> str:
        message = sanitize_sensitive_text(
            record.getMessage(),
            max_length=_DEFAULT_MESSAGE_LIMIT,
        )
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(
                record.created,
                tz=timezone.utc,
            ).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "event": _safe_string(getattr(record, "event", "application_log")),
            "message": message,
            "trace_id": _safe_string(
                getattr(record, "trace_id", None) or current_trace_id()
            ),
        }
        for field_name in _STRUCTURED_FIELDS:
            if not hasattr(record, field_name):
                continue
            payload[field_name] = _safe_log_value(
                getattr(record, field_name),
                max_length=_DEFAULT_MESSAGE_LIMIT,
            )

        if record.exc_info:
            exception_type = record.exc_info[0]
            if exception_type is not None:
                payload["exception_type"] = exception_type.__name__
            payload["stack_trace"] = sanitize_sensitive_text(
                self.formatException(record.exc_info)
            )
        elif record.exc_text:
            payload["stack_trace"] = sanitize_sensitive_text(record.exc_text)

        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def configure_file_logging(
    settings: FileLoggingSettings | None = None,
    *,
    logger: logging.Logger | None = None,
) -> RotatingFileHandler | None:
    """Attach one rotating JSONL handler to the application logger."""

    resolved_settings = settings or FileLoggingSettings.from_env()
    if not resolved_settings.enabled:
        return None

    target_logger = logger or logging.getLogger("app")
    for existing_handler in target_logger.handlers:
        if getattr(existing_handler, _HANDLER_MARKER, False):
            return existing_handler  # type: ignore[return-value]

    resolved_settings.path.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        resolved_settings.path,
        maxBytes=resolved_settings.max_bytes,
        backupCount=resolved_settings.backup_count,
        encoding="utf-8",
    )
    setattr(handler, _HANDLER_MARKER, True)
    handler.setLevel(resolved_settings.level)
    handler.setFormatter(JsonLineFormatter())
    target_logger.setLevel(resolved_settings.level)
    target_logger.addHandler(handler)
    target_logger.propagate = True
    target_logger.info(
        "Application file logging configured.",
        extra={"event": "application_logging_configured"},
    )
    return handler


def remove_file_logging_handler(*, logger: logging.Logger | None = None) -> None:
    """Remove and close configured file handlers; primarily useful for tests."""

    target_logger = logger or logging.getLogger("app")
    for handler in list(target_logger.handlers):
        if not getattr(handler, _HANDLER_MARKER, False):
            continue
        target_logger.removeHandler(handler)
        handler.close()


def bind_trace_id(trace_id: str) -> Token[str | None]:
    """Bind a request trace id to the current asynchronous execution context."""

    return _TRACE_ID.set(trace_id.strip() or None)


def reset_trace_id(token: Token[str | None]) -> None:
    """Restore the trace context that existed before ``bind_trace_id``."""

    _TRACE_ID.reset(token)


def current_trace_id() -> str | None:
    """Return the trace id bound to the current asynchronous context."""

    return _TRACE_ID.get()


def retrieval_query_log_fields(query: str | None) -> dict[str, str | None]:
    """Return bounded query text and a stable privacy-conscious fingerprint."""

    normalized_query = " ".join(query.split()) if query else ""
    if not normalized_query:
        return {"generated_query": None, "query_fingerprint": None}

    return {
        "generated_query": normalized_query[:_QUERY_TEXT_LIMIT],
        "query_fingerprint": hashlib.sha256(
            normalized_query.casefold().encode("utf-8")
        ).hexdigest()[:16],
    }


def exception_diagnostic_fields(error: BaseException) -> dict[str, Any]:
    """Extract allow-listed provider diagnostics without serializing raw payloads."""

    fields: dict[str, Any] = {"exception_type": type(error).__name__}
    attribute_mapping = {
        "status_code": "provider_http_status",
        "provider_code": "provider_error_code",
        "request_id": "provider_request_id",
        "finish_reason": "finish_reason",
    }
    for attribute_name, field_name in attribute_mapping.items():
        value = getattr(error, attribute_name, None)
        if value is not None:
            fields[field_name] = value
    return fields


def sanitize_sensitive_text(
    value: object,
    *,
    max_length: int | None = None,
) -> str:
    """Redact explicit credential shapes while preserving diagnostic text."""

    text = str(value)
    text = _BEARER_PATTERN.sub(r"\1[REDACTED]", text)
    text = _CREDENTIAL_PATTERN.sub(r"\1[REDACTED]", text)
    if max_length is not None and len(text) > max_length:
        return text[: max_length - 3].rstrip() + "..."
    return text


def _safe_log_value(value: Any, *, max_length: int) -> Any:
    if value is None or isinstance(value, bool | int | float):
        return value
    if isinstance(value, Enum):
        return _safe_log_value(value.value, max_length=max_length)
    if isinstance(value, list | tuple):
        return [
            _safe_log_value(item, max_length=max_length)
            for item in value
        ]
    return sanitize_sensitive_text(value, max_length=max_length)


def _safe_string(value: object) -> str | None:
    if value is None:
        return None
    return sanitize_sensitive_text(value, max_length=_DEFAULT_MESSAGE_LIMIT)


def _boolean_env(name: str, *, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None or not raw_value.strip():
        return default
    normalized = raw_value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean value.")


def _positive_int_env(name: str, *, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None or not raw_value.strip():
        return default
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer.") from exc
    if value <= 0:
        raise ValueError(f"{name} must be greater than 0.")
    return value


def _log_level(raw_value: str) -> int:
    normalized = raw_value.strip().upper() or "INFO"
    level = logging.getLevelName(normalized)
    if not isinstance(level, int):
        raise ValueError("APP_LOG_LEVEL must be a valid Python logging level.")
    return level


def _log_path(raw_value: str) -> Path:
    path = Path(raw_value.strip() or "logs/app.jsonl").expanduser()
    if path.is_absolute():
        return path
    project_root = Path(__file__).resolve().parents[2]
    return project_root / path


__all__ = [
    "FileLoggingSettings",
    "JsonLineFormatter",
    "bind_trace_id",
    "configure_file_logging",
    "current_trace_id",
    "exception_diagnostic_fields",
    "remove_file_logging_handler",
    "reset_trace_id",
    "retrieval_query_log_fields",
    "sanitize_sensitive_text",
]
