from __future__ import annotations

from types import SimpleNamespace
from pathlib import Path

from local_llm_proxy.config import Settings
from local_llm_proxy.services import proxy


def _settings(tmp_path: Path) -> Settings:
    key_path = tmp_path / ".litellm_virtual_key"
    return Settings(
        script_dir=tmp_path,
        config_dir=tmp_path,
        env_file=tmp_path / ".env",
        compose_file=tmp_path / "docker-compose.yml",
        virtual_key_file=key_path,
        ollama_model="gemma3:12b",
        ollama_host="http://localhost:11434",
        litellm_port="4000",
        litellm_master_key="master",
    )


def test_start_proxy_happy_path(monkeypatch, tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    commands: list[list[str]] = []

    def _capture(command: list[str], **kwargs) -> None:
        commands.append(command)

    monkeypatch.setattr(proxy, "run_command", _capture)
    monkeypatch.setattr(proxy, "_wait_for_readiness", lambda **kwargs: None)
    monkeypatch.setattr(proxy, "_seed_virtual_key", lambda *_: "vk")
    monkeypatch.setattr(proxy, "_wait_for_ngrok_url", lambda **kwargs: "https://example.ngrok.io")

    result = proxy.start_proxy(settings)

    assert result == {"public_url": "https://example.ngrok.io", "virtual_key": "vk"}
    assert commands == [
        [
            "docker",
            "compose",
            "-f",
            str(settings.compose_file),
            "--env-file",
            str(settings.env_file),
            "up",
            "-d",
        ]
    ]


def test_stop_proxy_runs_compose_down(monkeypatch, tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    called: list[list[str]] = []

    def _capture(command: list[str], **kwargs) -> None:
        called.append(command)

    monkeypatch.setattr(proxy, "run_command", _capture)
    proxy.stop_proxy(settings)

    assert called
    assert called[0][-2:] == ["down", "--remove-orphans"]


def test_seed_virtual_key_uses_cached_file(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    settings.virtual_key_file.write_text("cached-key\n", encoding="utf-8")
    assert proxy._seed_virtual_key(settings) == "cached-key"


def test_seed_virtual_key_generates_and_writes(monkeypatch, tmp_path: Path) -> None:
    settings = _settings(tmp_path)

    def _fake_get(*_args, **_kwargs):
        return SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {"data": [{"id": "model-a.local"}]},
        )

    def _fake_post(*_args, **_kwargs):
        return SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {"key": "generated-key"},
        )

    monkeypatch.setattr(proxy.requests, "get", _fake_get)
    monkeypatch.setattr(proxy.requests, "post", _fake_post)

    key = proxy._seed_virtual_key(settings)
    assert key == "generated-key"
    assert settings.virtual_key_file.read_text(encoding="utf-8").strip() == "generated-key"
