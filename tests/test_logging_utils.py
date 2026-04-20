from __future__ import annotations

import json

import pytest

from local_llm_proxy import logging_utils


def test_log_defaults_to_colorized_text(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[tuple[str, bool]] = []

    monkeypatch.delenv("LOCAL_LLM_PROXY_LOG_FORMAT", raising=False)
    monkeypatch.setattr(logging_utils, "_timestamp", lambda: "2026-04-20T10:00:00+00:00")
    monkeypatch.setattr(
        logging_utils.click,
        "echo",
        lambda message, err=False: captured.append((message, err)),
    )

    logging_utils.log("hello world")

    assert len(captured) == 1
    message, err = captured[0]
    assert err is False
    assert "[INFO]" in message
    assert "hello world" in message
    assert "\x1b[" in message


def test_log_text_includes_sorted_json_context(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[tuple[str, bool]] = []

    monkeypatch.setenv("LOCAL_LLM_PROXY_LOG_FORMAT", "text")
    monkeypatch.setattr(logging_utils, "_timestamp", lambda: "2026-04-20T10:00:00+00:00")
    monkeypatch.setattr(
        logging_utils.click,
        "echo",
        lambda message, err=False: captured.append((message, err)),
    )

    logging_utils.log("ctx", zeta=2, alpha={"ok": True})

    message, err = captured[0]
    assert err is False
    assert 'alpha={"ok":true}' in message
    assert "zeta=2" in message
    assert message.index('alpha={"ok":true}') < message.index("zeta=2")


def test_log_json_format_emits_structured_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[tuple[str, bool]] = []

    monkeypatch.setenv("LOCAL_LLM_PROXY_LOG_FORMAT", "json")
    monkeypatch.setattr(logging_utils, "_timestamp", lambda: "2026-04-20T10:00:00+00:00")
    monkeypatch.setattr(
        logging_utils.click,
        "echo",
        lambda message, err=False: captured.append((message, err)),
    )

    logging_utils.log("json-log", model="gemma3:4b")

    message, err = captured[0]
    assert err is False
    payload = json.loads(message)
    assert payload == {
        "timestamp": "2026-04-20T10:00:00+00:00",
        "level": "info",
        "message": "json-log",
        "context": {"model": "gemma3:4b"},
    }


def test_err_writes_to_stderr(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[tuple[str, bool]] = []

    monkeypatch.delenv("LOCAL_LLM_PROXY_LOG_FORMAT", raising=False)
    monkeypatch.setattr(logging_utils, "_timestamp", lambda: "2026-04-20T10:00:00+00:00")
    monkeypatch.setattr(
        logging_utils.click,
        "echo",
        lambda message, err=False: captured.append((message, err)),
    )

    logging_utils.err("boom")

    message, err = captured[0]
    assert err is True
    assert "[ERROR]" in message
    assert "boom" in message


def test_trace_only_logs_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[tuple[str, bool]] = []

    monkeypatch.delenv("LOCAL_LLM_PROXY_TRACE", raising=False)
    monkeypatch.delenv("LOCAL_LLM_PROXY_LOG_FORMAT", raising=False)
    monkeypatch.setattr(logging_utils, "_timestamp", lambda: "2026-04-20T10:00:00+00:00")
    monkeypatch.setattr(
        logging_utils.click,
        "echo",
        lambda message, err=False: captured.append((message, err)),
    )

    logging_utils.trace("hidden")
    assert captured == []

    monkeypatch.setenv("LOCAL_LLM_PROXY_TRACE", "1")
    logging_utils.trace("shown")

    assert len(captured) == 1
    message, err = captured[0]
    assert err is False
    assert "[DEBUG]" in message
    assert "shown" in message


def test_timestamp_is_utc_offset() -> None:
    timestamp = logging_utils._timestamp()
    assert timestamp.endswith("+00:00")
