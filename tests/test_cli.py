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
        litellm_ollama_model="ollama/gemma3:12b",
        litellm_model_name="ollama/gemma3:12b.ollama",
    )


def test_setup_start_success_local_only(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("local_llm_proxy.cli.load_settings", _settings)

    config_file = tmp_path / "litellm.yaml"
    config_file.write_text("model_list: []\n", encoding="utf-8")

    captured: dict[str, object] = {}

    def _start(_settings, *, litellm_config_file, public):
        captured["path"] = litellm_config_file
        captured["public"] = public
        return {"public_url": "", "virtual_key": "vk"}

    monkeypatch.setattr("local_llm_proxy.cli.start_proxy", _start)

    result = CliRunner().invoke(
        cli,
        ["setup", "start", "--litellm-config", str(config_file)],
    )
    assert result.exit_code == 0
    assert "LiteLLM local endpoint: http://localhost:4000" in result.output
    assert captured["path"] == config_file
    assert captured["public"] is False


def test_setup_start_success_public(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("local_llm_proxy.cli.load_settings", _settings)

    config_file = tmp_path / "litellm.yaml"
    config_file.write_text("model_list: []\n", encoding="utf-8")

    captured: dict[str, object] = {}

    def _start(_settings, *, litellm_config_file, public):
        captured["path"] = litellm_config_file
        captured["public"] = public
        return {"public_url": "https://abc.ngrok.io", "virtual_key": "vk"}

    monkeypatch.setattr("local_llm_proxy.cli.start_proxy", _start)

    result = CliRunner().invoke(
        cli,
        ["setup", "start", "--public", "--litellm-config", str(config_file)],
    )
    assert result.exit_code == 0
    assert "Public ngrok URL: https://abc.ngrok.io" in result.output
    assert captured["public"] is True


def test_setup_start_uses_default_litellm_config(monkeypatch, tmp_path: Path) -> None:
    repo_root = tmp_path
    cfg = repo_root / "config"
    cfg.mkdir(parents=True)
    default_cfg = cfg / "litellm-config.yaml"
    default_cfg.write_text("model_list: []\n", encoding="utf-8")

    def _settings_local() -> Settings:
        return Settings(
            repo_root=repo_root,
            config_dir=cfg,
            env_file=cfg / ".env",
            compose_file=cfg / "docker-compose.yml",
            virtual_key_file=cfg / ".litellm_virtual_key",
            ollama_model="gemma3:12b",
            ollama_host="http://localhost:11434",
            litellm_port="4000",
            litellm_master_key="master",
            litellm_ollama_model="ollama/gemma3:12b",
            litellm_model_name="ollama/gemma3:12b.ollama",
        )

    monkeypatch.setattr("local_llm_proxy.cli.load_settings", _settings_local)

    captured: dict[str, object] = {}

    def _start(_settings, *, litellm_config_file, public):
        captured["path"] = litellm_config_file
        captured["public"] = public
        return {"public_url": "", "virtual_key": "vk"}

    monkeypatch.setattr("local_llm_proxy.cli.start_proxy", _start)

    result = CliRunner().invoke(cli, ["setup", "start"])
    assert result.exit_code == 0
    assert captured["path"] == default_cfg
    assert captured["public"] is False


def test_setup_start_failure(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("local_llm_proxy.cli.load_settings", _settings)

    config_file = tmp_path / "litellm.yaml"
    config_file.write_text("model_list: []\n", encoding="utf-8")

    def _raise(_settings, *, litellm_config_file, public) -> None:
        _ = litellm_config_file
        _ = public
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


def test_setup_stop_runtime_error_is_click_exception(monkeypatch) -> None:
    monkeypatch.setattr("local_llm_proxy.cli.load_settings", _settings)

    def _raise(_settings) -> None:
        raise RuntimeError("stop failed")

    monkeypatch.setattr("local_llm_proxy.cli.stop_proxy", _raise)
    result = CliRunner().invoke(cli, ["setup", "stop"])
    assert result.exit_code != 0
    assert "stop failed" in result.output


def test_validate_command_success(monkeypatch) -> None:
    monkeypatch.setattr("local_llm_proxy.cli.load_settings", _settings)

    class _Result:
        content = "hello world"

    monkeypatch.setattr("local_llm_proxy.cli.validate_setup", lambda _settings: _Result())
    result = CliRunner().invoke(cli, ["validate"])
    assert result.exit_code == 0
    assert "Validation response: hello world" in result.output
