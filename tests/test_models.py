from __future__ import annotations

import pytest

from local_llm_proxy.services import models


def test_add_model_invokes_ollama_pull(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def fake_run_command(command: list[str], **_: object) -> None:
        calls.append(command)

    monkeypatch.setattr(models, "run_command", fake_run_command)
    models.add_model("gemma3:4b")

    assert calls == [["ollama", "pull", "gemma3:4b"]]


def test_remove_model_invokes_ollama_rm(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def fake_run_command(command: list[str], **_: object) -> None:
        calls.append(command)

    monkeypatch.setattr(models, "run_command", fake_run_command)
    models.remove_model("gemma3:4b")

    assert calls == [["ollama", "rm", "gemma3:4b"]]


def test_list_models_invokes_ollama_list(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def fake_run_command(command: list[str], **_: object) -> None:
        calls.append(command)

    monkeypatch.setattr(models, "run_command", fake_run_command)
    models.list_models()

    assert calls == [["ollama", "list"]]
