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


@pytest.mark.parametrize(
    ("command", "error_prefix", "expected_message"),
    [
        ([], None, "Invalid empty command list"),
        ([], "setup start", "setup start: Invalid empty command list"),
    ],
)
def test_run_command_rejects_empty_command(command: list[str], error_prefix: str | None, expected_message: str) -> None:
    with pytest.raises(RuntimeError, match=expected_message):
        process_utils.run_command(command, error_prefix=error_prefix)


def test_run_command_wraps_timeout_expired(monkeypatch: pytest.MonkeyPatch) -> None:
    traces: list[tuple[str, dict[str, object]]] = []

    def _trace(message: str, **kwargs: object) -> None:
        traces.append((message, kwargs))

    def _raise_timeout(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(cmd=["echo", "hi"], timeout=1)

    monkeypatch.setattr(process_utils, "trace", _trace)
    monkeypatch.setattr(process_utils.subprocess, "run", _raise_timeout)

    with pytest.raises(RuntimeError) as exc_info:
        process_utils.run_command(["sleep", "10"], timeout=1)

    message = str(exc_info.value)
    assert message == "Command timed out: sleep 10"

    assert traces
    assert traces[0][0] == "Executing command"
    assert traces[0][1]["command"] == ["sleep", "10"]
    assert traces[1][0] == "Command timed out"
    assert traces[1][1]["command"] == ["sleep", "10"]
    assert traces[1][1]["detail"] == "Command timed out: sleep 10"


def test_run_command_wraps_timeout_expired_with_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise_timeout(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(cmd=["sleep", "10"], timeout=1)

    monkeypatch.setattr(process_utils.subprocess, "run", _raise_timeout)

    with pytest.raises(RuntimeError, match="long task: Command timed out: sleep 10"):
        process_utils.run_command(["sleep", "10"], timeout=1, error_prefix="long task")
