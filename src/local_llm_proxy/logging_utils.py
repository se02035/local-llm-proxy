"""Structured logging helpers for CLI output consistency."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

import click


def _timestamp() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def _trace_enabled() -> bool:
    value = os.getenv("LOCAL_LLM_PROXY_TRACE", "")
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _log_format() -> str:
    value = os.getenv("LOCAL_LLM_PROXY_LOG_FORMAT", "text").strip().lower()
    if value in {"json", "text"}:
        return value
    return "text"


def _colorized_level(level: str) -> str:
    normalized = level.upper()
    color = {
        "DEBUG": "cyan",
        "INFO": "green",
        "ERROR": "red",
    }.get(normalized, "white")
    return click.style(f"[{normalized}]", fg=color, bold=True)


def _format_text(level: str, message: str, *, context: dict[str, Any]) -> str:
    base = f"{_colorized_level(level)} {_timestamp()}: {message}"
    if not context:
        return base
    context_fields = " ".join(
        f"{key}={json.dumps(value, separators=(',', ':'), default=str)}" for key, value in sorted(context.items())
    )
    return f"{base} {context_fields}"


def _emit(level: str, message: str, *, err: bool = False, **context: Any) -> None:
    if _log_format() == "json":
        payload: dict[str, Any] = {"timestamp": _timestamp(), "level": level, "message": message}
        if context:
            payload["context"] = context
        click.echo(json.dumps(payload, separators=(",", ":"), default=str), err=err)
        return

    click.echo(_format_text(level, message, context=context), err=err)


def log(message: str, **context: Any) -> None:
    """Emit an informational structured log event.

    Args:
        message: Message content for the event body.
        **context: Optional key/value metadata included under `context`.

    Returns:
        None: Writes formatted log output to stdout.
    """
    _emit("info", message, **context)


def err(message: str, **context: Any) -> None:
    """Emit an error structured log event.

    Args:
        message: Message content for the event body.
        **context: Optional key/value metadata included under `context`.

    Returns:
        None: Writes formatted log output to stderr.
    """
    _emit("error", message, err=True, **context)


def trace(message: str, **context: Any) -> None:
    """Emit a debug structured log event when tracing is enabled.

    Args:
        message: Message content for the event body.
        **context: Optional key/value metadata included under `context`.

    Returns:
        None: Writes formatted log output to stdout when trace is enabled.
    """
    if _trace_enabled():
        _emit("debug", message, **context)
