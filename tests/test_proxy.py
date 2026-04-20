from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from local_llm_proxy.config import Settings
from local_llm_proxy.services import proxy


def _settings(tmp_path: Path) -> Settings:
    key_path = tmp_path / ".litellm_virtual_key"
    return Settings(
        repo_root=tmp_path,
        config_dir=tmp_path,
        env_file=tmp_path / ".env",
        compose_file=tmp_path / "docker-compose.yml",
        virtual_key_file=key_path,
        ollama_model="gemma3:12b",
        ollama_host="http://localhost:11434",
        litellm_port="4000",
        litellm_master_key="master",
        litellm_ollama_model="ollama/gemma3:12b",
        litellm_model_name="ollama/gemma3:12b.ollama",
    )


def test_start_proxy_happy_path_local_only(monkeypatch, tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    settings.env_file.write_text("LITELLM_PORT=4000\n", encoding="utf-8")
    commands: list[list[str]] = []
    command_kwargs: list[dict] = []

    def _capture(command: list[str], **kwargs) -> None:
        commands.append(command)
        command_kwargs.append(kwargs)

    monkeypatch.setattr(proxy, "run_command", _capture)
    monkeypatch.setattr(proxy, "_wait_for_readiness", lambda **kwargs: None)
    monkeypatch.setattr(proxy, "_seed_virtual_key", lambda *_: "vk")

    result = proxy.start_proxy(
        settings,
        litellm_config_file=Path("/tmp/litellm.yaml"),
        public=False,
    )

    assert result == {"public_url": "", "virtual_key": "vk"}
    assert commands == [
        [
            "docker",
            "compose",
            "-p",
            "local-llm-proxy",
            "-f",
            str(settings.compose_file),
            "--env-file",
            str(settings.env_file),
            "up",
            "-d",
        ]
    ]
    assert command_kwargs[0]["env"]["LITELLM_CONFIG_FILE"] == "/tmp/litellm.yaml"


def test_compose_command_omits_env_file_when_missing(tmp_path: Path) -> None:
    settings = _settings(tmp_path)

    command = proxy._compose_command(settings, public=False)

    assert "--env-file" not in command


def test_start_proxy_happy_path_public(monkeypatch, tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    commands: list[list[str]] = []
    captured: dict[str, int] = {}

    def _capture(command: list[str], **kwargs) -> None:
        commands.append(command)

    monkeypatch.setattr(proxy, "run_command", _capture)
    monkeypatch.setattr(proxy, "_wait_for_readiness", lambda **kwargs: None)
    monkeypatch.setattr(proxy, "_seed_virtual_key", lambda *_: "vk")

    def _wait_for_ngrok_url(*, timeout_seconds: int) -> str:
        captured["timeout_seconds"] = timeout_seconds
        return "https://example.ngrok.io"

    monkeypatch.setattr(proxy, "_wait_for_ngrok_url", _wait_for_ngrok_url)

    result = proxy.start_proxy(settings, public=True, timeout_seconds=42)

    assert result == {"public_url": "https://example.ngrok.io", "virtual_key": "vk"}
    assert "--profile" in commands[0]
    assert "public" in commands[0]
    assert captured["timeout_seconds"] == 42


def test_start_proxy_failure_includes_compose_diagnostics(monkeypatch, tmp_path: Path) -> None:
    settings = _settings(tmp_path)

    def _capture(command: list[str], **kwargs):
        _ = kwargs
        if command[-2:] == ["up", "-d"]:
            raise RuntimeError("Failed to start docker compose services: exit 1")
        if command[-2:] == ["ps", "--all"]:
            return SimpleNamespace(stdout="litellm-proxy unhealthy\n", stderr="")
        if "logs" in command:
            return SimpleNamespace(stdout="litellm-proxy | startup failed\n", stderr="")
        raise AssertionError(f"Unexpected command: {command}")

    monkeypatch.setattr(proxy, "run_command", _capture)

    with pytest.raises(RuntimeError) as exc_info:
        proxy.start_proxy(settings, public=True)

    message = str(exc_info.value)
    assert "Failed to start docker compose services." in message
    assert "Actionable next steps:" in message
    assert "Container `litellm-proxy` became unhealthy." in message
    assert "Original error: Failed to start docker compose services: exit 1" in message
    assert "Additional docker compose diagnostics:" in message
    assert "docker compose ps --all:" in message
    assert "litellm-proxy unhealthy" in message
    assert "docker compose logs --no-color --tail 120:" in message
    assert "litellm-proxy | startup failed" in message


def test_compose_failure_guidance_includes_public_hint() -> None:
    settings = _settings(Path("/tmp"))
    guidance = proxy._compose_failure_guidance(
        error_message="boom",
        diagnostics="",
        public=True,
        settings=settings,
    )
    assert "Actionable next steps:" in guidance
    assert "docker compose -p local-llm-proxy" in guidance
    assert "-f /tmp/docker-compose.yml --profile public ps --all" in guidance
    assert "If using `--public`, verify `NGROK_AUTHTOKEN` is set correctly" in guidance


def test_stop_proxy_runs_compose_down(monkeypatch, tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    called: list[list[str]] = []

    def _capture(command: list[str], **kwargs) -> None:
        called.append(command)

    monkeypatch.setattr(proxy, "run_command", _capture)
    proxy.stop_proxy(settings)

    assert called
    assert "--profile" in called[0]
    assert "public" in called[0]
    assert called[0][-2:] == ["down", "--remove-orphans"]


def test_running_compose_services_returns_empty_on_command_failure(monkeypatch, tmp_path: Path) -> None:
    settings = _settings(tmp_path)

    def _raise(*_args, **_kwargs):
        raise RuntimeError("compose unavailable")

    monkeypatch.setattr(proxy, "run_command", _raise)

    assert proxy._running_compose_services(settings) == set()


def test_get_proxy_status_only_includes_running_services(monkeypatch, tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    settings.virtual_key_file.write_text("vk\n", encoding="utf-8")

    monkeypatch.setattr(proxy, "_running_compose_services", lambda _settings: {"ngrok"})

    def _fake_get(*_args, **_kwargs):
        return SimpleNamespace(ok=True, json=lambda: {"tunnels": [{"public_url": "https://abc.ngrok.io"}]})

    monkeypatch.setattr(proxy.requests, "get", _fake_get)

    status = proxy.get_proxy_status(settings)

    assert status["litellm_running"] is False
    assert status["local_endpoint"] == ""
    assert status["local_admin_url"] == ""
    assert status["virtual_key"] == ""
    assert status["ngrok_running"] is True
    assert status["ngrok_admin_url"] == "http://localhost:4040"
    assert status["public_url"] == "https://abc.ngrok.io"


def test_get_proxy_status_with_litellm_running_sets_local_urls(monkeypatch, tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    settings.virtual_key_file.write_text("vk\n", encoding="utf-8")
    monkeypatch.setattr(proxy, "_running_compose_services", lambda _settings: {"litellm"})

    status = proxy.get_proxy_status(settings)

    assert status["litellm_running"] is True
    assert status["local_endpoint"] == "http://localhost:4000"
    assert status["local_admin_url"] == "http://localhost:4000/ui/"
    assert status["virtual_key"] == "vk"
    assert status["ngrok_running"] is False
    assert status["ngrok_admin_url"] == ""
    assert status["public_url"] == ""


def test_seed_virtual_key_uses_cached_file(monkeypatch, tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    settings.virtual_key_file.write_text("cached-key\n", encoding="utf-8")
    monkeypatch.setattr(proxy.requests, "get", lambda *args, **kwargs: SimpleNamespace(ok=True))
    assert proxy._seed_virtual_key(settings) == "cached-key"


def test_seed_virtual_key_generates_and_writes(monkeypatch, tmp_path: Path) -> None:
    settings = _settings(tmp_path)

    def _fake_get(url: str, **_kwargs):
        assert url == "http://localhost:4000/v1/models"
        return SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {"data": [{"id": "model-a.local"}]},
        )

    def _fake_post(url: str, **_kwargs):
        assert url == "http://localhost:4000/key/generate"
        return SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {"key": "generated-key"},
        )

    monkeypatch.setattr(proxy.requests, "get", _fake_get)
    monkeypatch.setattr(proxy.requests, "post", _fake_post)

    key = proxy._seed_virtual_key(settings)
    assert key == "generated-key"
    assert settings.virtual_key_file.read_text(encoding="utf-8").strip() == "generated-key"
    assert oct(settings.virtual_key_file.stat().st_mode & 0o777) == "0o600"


def test_seed_virtual_key_regenerates_when_cached_key_invalid(monkeypatch, tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    settings.virtual_key_file.write_text("stale-key\n", encoding="utf-8")

    def _fake_get(url: str, **kwargs):
        auth_header = kwargs.get("headers", {}).get("Authorization")
        if auth_header == "Bearer stale-key":
            return SimpleNamespace(ok=False)
        assert auth_header == "Bearer master"
        return SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {"data": [{"id": "model-a.local"}]},
        )

    def _fake_post(url: str, **_kwargs):
        assert url == "http://localhost:4000/key/generate"
        return SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {"key": "regenerated-key"},
        )

    monkeypatch.setattr(proxy.requests, "get", _fake_get)
    monkeypatch.setattr(proxy.requests, "post", _fake_post)

    key = proxy._seed_virtual_key(settings)
    assert key == "regenerated-key"
    assert settings.virtual_key_file.read_text(encoding="utf-8").strip() == "regenerated-key"


def test_seed_virtual_key_urls_use_litellm_port(monkeypatch, tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    settings = Settings(
        repo_root=settings.repo_root,
        config_dir=settings.config_dir,
        env_file=settings.env_file,
        compose_file=settings.compose_file,
        virtual_key_file=settings.virtual_key_file,
        ollama_model=settings.ollama_model,
        ollama_host=settings.ollama_host,
        litellm_port="5000",
        litellm_master_key=settings.litellm_master_key,
        litellm_ollama_model=settings.litellm_ollama_model,
        litellm_model_name=settings.litellm_model_name,
    )

    def _fake_get(url: str, **_kwargs):
        assert url == "http://localhost:5000/v1/models"
        return SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {"data": []},
        )

    def _fake_post(url: str, **_kwargs):
        assert url == "http://localhost:5000/key/generate"
        return SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {"key": "k2"},
        )

    monkeypatch.setattr(proxy.requests, "get", _fake_get)
    monkeypatch.setattr(proxy.requests, "post", _fake_post)

    assert proxy._seed_virtual_key(settings) == "k2"


def test_seed_virtual_key_request_errors_are_wrapped(monkeypatch, tmp_path: Path) -> None:
    import requests

    settings = _settings(tmp_path)

    def _raise(*_args, **_kwargs):
        raise requests.RequestException("network fail")

    monkeypatch.setattr(proxy.requests, "get", _raise)

    with pytest.raises(RuntimeError, match="Failed to seed LiteLLM virtual key"):
        proxy._seed_virtual_key(settings)
