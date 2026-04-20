from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from local_llm_proxy.cli import cli
from local_llm_proxy.config import Settings


def _settings() -> Settings:
    return Settings(
        script_dir=Path("/tmp"),
        config_dir=Path("/tmp"),
        env_file=Path("/tmp/.env"),
        compose_file=Path("/tmp/docker-compose.yml"),
        virtual_key_file=Path("/tmp/.litellm_virtual_key"),
        ollama_model="gemma3:12b",
        ollama_host="http://localhost:11434",
        litellm_port="4000",
        litellm_master_key="master",
    )


def test_setup_start_success(monkeypatch) -> None:
    monkeypatch.setattr("local_llm_proxy.cli.load_settings", _settings)
    monkeypatch.setattr(
        "local_llm_proxy.cli.start_proxy",
        lambda _settings: {"public_url": "https://abc.ngrok.io", "virtual_key": "vk"},
    )

    result = CliRunner().invoke(cli, ["setup", "start"])
    assert result.exit_code == 0
    assert "Public ngrok URL: https://abc.ngrok.io" in result.output


def test_setup_start_failure(monkeypatch) -> None:
    monkeypatch.setattr("local_llm_proxy.cli.load_settings", _settings)

    def _raise(_settings) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr("local_llm_proxy.cli.start_proxy", _raise)

    result = CliRunner().invoke(cli, ["setup", "start"])
    assert result.exit_code != 0
    assert "boom" in result.output


def test_validate_command_success(monkeypatch) -> None:
    monkeypatch.setattr("local_llm_proxy.cli.load_settings", _settings)

    class _Result:
        content = "hello world"

    monkeypatch.setattr("local_llm_proxy.cli.validate_setup", lambda _settings: _Result())
    result = CliRunner().invoke(cli, ["validate"])
    assert result.exit_code == 0
    assert "Validation response: hello world" in result.output
