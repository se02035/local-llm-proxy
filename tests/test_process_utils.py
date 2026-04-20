from __future__ import annotations

import subprocess

import pytest

from local_llm_proxy.services import process_utils


def test_output_uses_run_command(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def _run_command(command, *, capture_output=False, error_prefix=None):
        captured["command"] = command
        captured["capture_output"] = capture_output
        captured["error_prefix"] = error_prefix
        return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

    monkeypatch.setattr(process_utils, "run_command", _run_command)
    assert process_utils.output(["echo", "hi"]) == "ok"
    assert captured == {
        "command": ["echo", "hi"],
        "capture_output": True,
        "error_prefix": None,
    }


def test_run_command_wraps_missing_binary() -> None:
    with pytest.raises(RuntimeError, match="Command not found"):
        process_utils.run_command(["definitely-not-a-real-command-xyz"])


def test_run_command_rejects_empty_command() -> None:
    with pytest.raises(RuntimeError, match="Invalid empty command list"):
        process_utils.run_command([])


def test_run_command_rejects_empty_command_with_prefix() -> None:
    with pytest.raises(RuntimeError, match="setup start: Invalid empty command list"):
        process_utils.run_command([], error_prefix="setup start")


@pytest.mark.parametrize("error_prefix", [None, "", "setup start"])
def test_run_command_wraps_timeout_expired(
    monkeypatch: pytest.MonkeyPatch,
    error_prefix: str | None,
) -> None:
    traces: list[tuple[str, dict[str, object]]] = []

    def _trace(message: str, **kwargs: object) -> None:
        traces.append((message, kwargs))

    def _raise_timeout(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(cmd=["echo", "hi"], timeout=1)

    monkeypatch.setattr(process_utils, "trace", _trace)
    monkeypatch.setattr(process_utils.subprocess, "run", _raise_timeout)

    with pytest.raises(RuntimeError) as exc_info:
        process_utils.run_command(["echo", "hi"], error_prefix=error_prefix)

    expected_detail = "Command timed out: echo hi"
    message = str(exc_info.value)
    assert expected_detail in message
    if error_prefix:
        assert message == f"{error_prefix}: {expected_detail}"
    else:
        assert message == expected_detail

    assert traces
    assert traces[0][0] == "Executing command"
    assert traces[0][1]["command"] == ["echo", "hi"]
    assert traces[1][0] == "Command timed out"
    assert traces[1][1]["command"] == ["echo", "hi"]
    assert traces[1][1]["detail"] == expected_detail
