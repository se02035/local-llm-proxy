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
