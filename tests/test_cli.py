from __future__ import annotations

from pathlib import Path
from typing import Any

from click.testing import CliRunner

from local_llm_proxy.cli import cli
from local_llm_proxy.config import Settings


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        repo_root=tmp_path,
        config_dir=tmp_path,
        env_file=tmp_path / ".env",
        compose_file=tmp_path / "docker-compose.yml",
        virtual_key_file=tmp_path / ".litellm_virtual_key",
        ollama_model="gemma3:12b",
        ollama_host="http://localhost:11434",
        litellm_port="4000",
        litellm_master_key="master",
        litellm_ollama_model="ollama/gemma3:12b",
        litellm_model_name="ollama/gemma3:12b.ollama",
    )


def assert_common_cli_output(
    result: Any,
    captured: dict[str, Any],
    public: bool = False,
    config_file: Path | None = None,
) -> None:
    assert result.exit_code == 0
    assert "| Field" in result.output
    assert "LiteLLM local endpoint" in result.output
    assert "http://localhost:4000" in result.output
    assert "LiteLLM local admin URL" in result.output
    assert "http://localhost:4000/ui/" in result.output
    if public:
        assert "Public ngrok URL" in result.output
        assert "https://abc.ngrok.io" in result.output
        assert "Ngrok admin URL" in result.output
        assert "http://localhost:4040" in result.output
        assert "LiteLLM public admin URL" in result.output
        assert "https://abc.ngrok.io/ui/" in result.output
    assert "Virtual key" in result.output
    assert "vk" in result.output
    if config_file:
        assert captured["path"] == config_file
    assert captured["public"] is public


def test_setup_start_success_local_only(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("local_llm_proxy.cli.load_settings", lambda: _settings(tmp_path))

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
    assert_common_cli_output(result, captured, public=False, config_file=config_file)


def test_setup_start_success_public(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("local_llm_proxy.cli.load_settings", lambda: _settings(tmp_path))

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
    assert_common_cli_output(result, captured, public=True, config_file=config_file)


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
    monkeypatch.setattr("local_llm_proxy.cli.load_settings", lambda: _settings(tmp_path))

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


def test_setup_start_missing_config_file(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("local_llm_proxy.cli.load_settings", lambda: _settings(tmp_path))
    result = CliRunner().invoke(
        cli,
        ["setup", "start", "--litellm-config", "does-not-exist.yaml"],
    )
    assert result.exit_code != 0
    assert "LiteLLM config file not found" in result.output


def test_setup_stop_runtime_error_is_click_exception(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("local_llm_proxy.cli.load_settings", lambda: _settings(tmp_path))

    def _raise(_settings) -> None:
        raise RuntimeError("stop failed")

    monkeypatch.setattr("local_llm_proxy.cli.stop_proxy", _raise)
    result = CliRunner().invoke(cli, ["setup", "stop"])
    assert result.exit_code != 0
    assert "stop failed" in result.output


def test_setup_restart_success_public_prints_admin_urls(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("local_llm_proxy.cli.load_settings", lambda: _settings(tmp_path))

    captured: dict[str, object] = {}

    def _restart(_settings, *, litellm_config_file=None, public=False):
        captured["public"] = public
        return {"public_url": "https://abc.ngrok.io", "virtual_key": "vk"}

    monkeypatch.setattr("local_llm_proxy.cli.restart_proxy", _restart)

    result = CliRunner().invoke(cli, ["setup", "restart", "--public"])
    assert_common_cli_output(result, captured, public=True)


def test_setup_status_with_public_url(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("local_llm_proxy.cli.load_settings", lambda: _settings(tmp_path))
    monkeypatch.setattr(
        "local_llm_proxy.cli.get_proxy_status",
        lambda _settings: {
            "local_endpoint": "http://localhost:4000",
            "local_admin_url": "http://localhost:4000/ui/",
            "ngrok_admin_url": "http://localhost:4040",
            "public_url": "https://abc.ngrok.io",
            "virtual_key": "vk",
        },
    )

    result = CliRunner().invoke(cli, ["setup", "status"])
    assert result.exit_code == 0
    assert "| Field" in result.output
    assert "LiteLLM local endpoint" in result.output
    assert "http://localhost:4000" in result.output
    assert "LiteLLM local admin URL" in result.output
    assert "http://localhost:4000/ui/" in result.output
    assert "Ngrok admin URL" in result.output
    assert "http://localhost:4040" in result.output
    assert "Public ngrok URL" in result.output
    assert "https://abc.ngrok.io" in result.output
    assert "LiteLLM public admin URL" in result.output
    assert "https://abc.ngrok.io/ui/" in result.output
    assert "Virtual key" in result.output
    assert "vk" in result.output


def test_setup_status_without_public_url_or_virtual_key(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("local_llm_proxy.cli.load_settings", lambda: _settings(tmp_path))
    monkeypatch.setattr(
        "local_llm_proxy.cli.get_proxy_status",
        lambda _settings: {
            "local_endpoint": "http://localhost:4000",
            "local_admin_url": "http://localhost:4000/ui/",
            "ngrok_admin_url": "http://localhost:4040",
            "public_url": "",
            "virtual_key": "",
        },
    )

    result = CliRunner().invoke(cli, ["setup", "status"])
    assert result.exit_code == 0
    assert "| Field" in result.output
    assert "LiteLLM local endpoint" in result.output
    assert "http://localhost:4000" in result.output
    assert "LiteLLM local admin URL" in result.output
    assert "http://localhost:4000/ui/" in result.output
    assert "Ngrok admin URL" in result.output
    assert "http://localhost:4040" in result.output
    assert "Public ngrok URL" not in result.output
    assert "LiteLLM public admin URL" not in result.output
    assert "Virtual key" in result.output
    assert "(not found)" in result.output


def test_validate_command_success(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("local_llm_proxy.cli.load_settings", lambda: _settings(tmp_path))

    class _Result:
        content = "hello world"

    monkeypatch.setattr("local_llm_proxy.cli.validate_setup", lambda _settings: _Result())
    result = CliRunner().invoke(cli, ["validate"])
    assert result.exit_code == 0
    assert "Validation response: hello world" in result.output


def test_validate_command_failure(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("local_llm_proxy.cli.load_settings", lambda: _settings(tmp_path))

    def _raise(_settings) -> None:
        raise RuntimeError("Validation check failed: missing components")

    monkeypatch.setattr("local_llm_proxy.cli.validate_setup", _raise)
    result = CliRunner().invoke(cli, ["validate"])
    assert result.exit_code != 0
    assert "Validation check failed: missing components" in result.output
