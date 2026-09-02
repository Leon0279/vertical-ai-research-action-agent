"""Tests for structured file logging and request trace context."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from pathlib import Path

from app.adapters.llm.zhipu_llm_client_error import ZhipuLLMClientError
from app.common.observability import (
    FileLoggingSettings,
    bind_trace_id,
    configure_file_logging,
    current_trace_id,
    exception_diagnostic_fields,
    remove_file_logging_handler,
    reset_trace_id,
    retrieval_query_log_fields,
)
from app.domain.enums import FamilyName


def _settings(path: Path, *, max_bytes: int = 100_000) -> FileLoggingSettings:
    return FileLoggingSettings(
        enabled=True,
        path=path,
        level=logging.INFO,
        max_bytes=max_bytes,
        backup_count=2,
    )


def _logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    remove_file_logging_handler(logger=logger)
    logger.handlers.clear()
    logger.propagate = False
    return logger


def _json_lines(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_file_logging_settings_read_supported_environment_values(
    tmp_path: Path,
    monkeypatch,
) -> None:
    log_path = tmp_path / "configured.jsonl"
    monkeypatch.setenv("APP_LOG_ENABLED", "true")
    monkeypatch.setenv("APP_LOG_PATH", str(log_path))
    monkeypatch.setenv("APP_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("APP_LOG_MAX_BYTES", "1234")
    monkeypatch.setenv("APP_LOG_BACKUP_COUNT", "3")

    settings = FileLoggingSettings.from_env()

    assert settings == FileLoggingSettings(
        enabled=True,
        path=log_path,
        level=logging.DEBUG,
        max_bytes=1234,
        backup_count=3,
    )


def test_jsonl_handler_writes_allowlisted_fields_and_redacts_credentials(
    tmp_path: Path,
) -> None:
    log_path = tmp_path / "nested" / "app.jsonl"
    logger = _logger("app.tests.observability.jsonl")
    handler = configure_file_logging(_settings(log_path), logger=logger)
    assert handler is not None

    token = bind_trace_id("trace-jsonl")
    try:
        logger.info(
            "Provider rejected Authorization: Bearer super-secret and api_key=key-secret.",
            extra={
                "event": "provider_failed",
                "selected_family": "web_search",
                "generated_query": "safe retrieval query",
                "candidate_action_modes": [
                    "refine_from_existing_state",
                    "external_acquisition",
                ],
                "allowed_source_families": [
                    FamilyName.DOCS_SEARCH,
                    FamilyName.WEB_SEARCH,
                ],
                "action_rationale": "api_key=rationale-secret " + ("x" * 2100),
                "failure_stage": "search_http",
                "failure_reason": "timeout",
                "error_category": "timeout",
                "attempt_error_info": "Authorization: Bearer attempt-secret",
                "provider_http_status": 504,
                "retryable": True,
                "prompt": "private prompt must not be serialized",
                "raw_response": "private provider response",
            },
        )
    finally:
        reset_trace_id(token)
        handler.flush()
        remove_file_logging_handler(logger=logger)

    records = _json_lines(log_path)
    record = records[-1]
    assert record["event"] == "provider_failed"
    assert record["trace_id"] == "trace-jsonl"
    assert record["selected_family"] == "web_search"
    assert record["generated_query"] == "safe retrieval query"
    assert record["candidate_action_modes"] == [
        "refine_from_existing_state",
        "external_acquisition",
    ]
    assert record["allowed_source_families"] == ["docs_search", "web_search"]
    assert len(str(record["action_rationale"])) == 2000
    assert record["failure_stage"] == "search_http"
    assert record["failure_reason"] == "timeout"
    assert record["error_category"] == "timeout"
    assert record["provider_http_status"] == 504
    assert record["retryable"] is True
    serialized = json.dumps(record, ensure_ascii=False)
    assert "super-secret" not in serialized
    assert "key-secret" not in serialized
    assert "private prompt" not in serialized
    assert "private provider response" not in serialized
    assert "rationale-secret" not in serialized
    assert "attempt-secret" not in serialized
    assert "[REDACTED]" in serialized


def test_jsonl_handler_preserves_stack_trace_and_provider_diagnostics(
    tmp_path: Path,
) -> None:
    log_path = tmp_path / "app.jsonl"
    logger = _logger("app.tests.observability.exception")
    handler = configure_file_logging(_settings(log_path), logger=logger)
    assert handler is not None

    error = ZhipuLLMClientError(
        "Provider failed with api_key=secret-value.",
        status_code=503,
        provider_code="service_unavailable",
        request_id="provider-request-1",
        finish_reason="length",
    )
    try:
        raise error
    except ZhipuLLMClientError as caught:
        logger.exception(
            "Structured provider failure.",
            extra={
                "event": "agent_run_failed",
                **exception_diagnostic_fields(caught),
            },
        )
    handler.flush()
    remove_file_logging_handler(logger=logger)

    record = _json_lines(log_path)[-1]
    assert record["exception_type"] == "ZhipuLLMClientError"
    assert record["provider_http_status"] == 503
    assert record["provider_error_code"] == "service_unavailable"
    assert record["provider_request_id"] == "provider-request-1"
    assert record["finish_reason"] == "length"
    assert "Traceback (most recent call last)" in str(record["stack_trace"])
    assert "secret-value" not in str(record["stack_trace"])


def test_file_logging_is_idempotent_and_rotates(tmp_path: Path) -> None:
    log_path = tmp_path / "app.jsonl"
    logger = _logger("app.tests.observability.rotation")
    settings = _settings(log_path, max_bytes=300)

    first_handler = configure_file_logging(settings, logger=logger)
    second_handler = configure_file_logging(settings, logger=logger)
    assert first_handler is second_handler
    assert len(logger.handlers) == 1

    for index in range(30):
        logger.info(
            "Rotation record " + ("x" * 120),
            extra={"event": "rotation_test", "attempt_index": index},
        )
    assert first_handler is not None
    first_handler.flush()
    remove_file_logging_handler(logger=logger)

    assert log_path.exists()
    assert (tmp_path / "app.jsonl.1").exists()
    assert not (tmp_path / "app.jsonl.3").exists()


def test_trace_context_is_isolated_between_async_tasks() -> None:
    async def worker(trace_id: str) -> tuple[str | None, str | None]:
        token = bind_trace_id(trace_id)
        try:
            before_yield = current_trace_id()
            await asyncio.sleep(0)
            return before_yield, current_trace_id()
        finally:
            reset_trace_id(token)

    async def run_workers() -> list[tuple[str | None, str | None]]:
        return await asyncio.gather(worker("trace-a"), worker("trace-b"))

    assert asyncio.run(run_workers()) == [
        ("trace-a", "trace-a"),
        ("trace-b", "trace-b"),
    ]
    assert current_trace_id() is None


def test_retrieval_query_log_fields_are_bounded_and_stable() -> None:
    raw_query = "  Retrieval\nquery  " + ("x" * 700)
    normalized = "Retrieval query " + ("x" * 700)

    fields = retrieval_query_log_fields(raw_query)

    assert fields["generated_query"] == normalized[:500]
    assert len(fields["generated_query"] or "") == 500
    assert fields["query_fingerprint"] == hashlib.sha256(
        normalized.casefold().encode("utf-8")
    ).hexdigest()[:16]
    assert retrieval_query_log_fields(raw_query) == fields
    assert retrieval_query_log_fields(None) == {
        "generated_query": None,
        "query_fingerprint": None,
    }
