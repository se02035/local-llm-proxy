from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from local_llm_proxy.cli import cli
from local_llm_proxy.config import Settings


def _settings() -> Settings:
    return Settings(
        repo_root=Path("/tmp"),
        config_dir=Path("/tmp"),
        env_file=Path("/tmp/.env"),
        compose_file=Path("/tmp/docker-compose.yml"),
        virtual_key_file=Path("/tmp/.litellm_virtual_key"),
        ollama_model="gemma3:12b",
        ollama_host="http://localhost:11434",
        litellm_port="4000",
        litellm_master_key="master",
    )


def test_setup_start_success(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("local_llm_proxy.cli.load_settings", _settings)

    config_file = tmp_path / "litellm.yaml"
    config_file.write_text("model_list: []\n", encoding="utf-8")

    captured: dict[str, object] = {}

    def _start(_settings, *, litellm_config_file):
        captured["path"] = litellm_config_file
        return {"public_url": "https://abc.ngrok.io", "virtual_key": "vk"}

    monkeypatch.setattr("local_llm_proxy.cli.start_proxy", _start)

    result = CliRunner().invoke(
        cli,
        ["setup", "start", "--litellm-config", str(config_file)],
    )
    assert result.exit_code == 0
    assert "Public ngrok URL: https://abc.ngrok.io" in result.output
    assert captured["path"] == config_file


def test_setup_start_failure(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("local_llm_proxy.cli.load_settings", _settings)

    config_file = tmp_path / "litellm.yaml"
    config_file.write_text("model_list: []\n", encoding="utf-8")

    def _raise(_settings, *, litellm_config_file) -> None:
        _ = litellm_config_file
        raise RuntimeError("boom")

    monkeypatch.setattr("local_llm_proxy.cli.start_proxy", _raise)

    result = CliRunner().invoke(
        cli,
        ["setup", "start", "--litellm-config", str(config_file)],
    )
    assert result.exit_code != 0
    assert "boom" in result.output


def test_setup_start_missing_config_file(monkeypatch) -> None:
    monkeypatch.setattr("local_llm_proxy.cli.load_settings", _settings)
    result = CliRunner().invoke(
        cli,
        ["setup", "start", "--litellm-config", "does-not-exist.yaml"],
    )
    assert result.exit_code != 0
    assert "LiteLLM config file not found" in result.output


def test_validate_command_success(monkeypatch) -> None:
    monkeypatch.setattr("local_llm_proxy.cli.load_settings", _settings)

    class _Result:
        content = "hello world"

    monkeypatch.setattr("local_llm_proxy.cli.validate_setup", lambda _settings: _Result())
    result = CliRunner().invoke(cli, ["validate"])
    assert result.exit_code == 0
    assert "Validation response: hello world" in result.output
