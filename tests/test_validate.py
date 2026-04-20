from __future__ import annotations

from pathlib import Path

import pytest

from local_llm_proxy.config import Settings
from local_llm_proxy.services.validate import _normalize_ping_host, validate_setup


class DummyResponse:
    def __init__(self, payload: dict, status_ok: bool = True) -> None:
        self._payload = payload
        self.ok = status_ok

    def raise_for_status(self) -> None:
        if not self.ok:
            raise RuntimeError("http error")

    def json(self) -> dict:
        return self._payload


def _settings() -> Settings:
    return Settings(
        repo_root=Path("/tmp"),
        config_dir=Path("/tmp"),
        env_file=Path("/tmp/.env"),
        compose_file=Path("/tmp/docker-compose.yml"),
        virtual_key_file=Path("/tmp/.litellm_virtual_key"),
        ollama_model="gemma3:4b",
        ollama_host="http://localhost:11434",
        litellm_port="4000",
        litellm_master_key="master",
        litellm_ollama_model="ollama/gemma3:4b",
        litellm_model_name="ollama/gemma3:4b.ollama",
    )


def test_validate_setup_success(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings()

    def fake_get(url: str, timeout: tuple[int, int]) -> DummyResponse:
        assert url.endswith("/api/tags")
        assert timeout == (5, 10)
        return DummyResponse({})

    def fake_post(
        url: str, headers: dict[str, str], json: dict, timeout: tuple[int, int]
    ) -> DummyResponse:
        assert "chat/completions" in url
        assert headers["Authorization"] == "Bearer master"
        assert json["model"] == "ollama/gemma3:4b.ollama"
        assert timeout == (5, 30)
        return DummyResponse({"choices": [{"message": {"content": "hello world"}}]})

    monkeypatch.setattr("local_llm_proxy.services.validate.requests.get", fake_get)
    monkeypatch.setattr("local_llm_proxy.services.validate.requests.post", fake_post)

    result = validate_setup(settings)
    assert result.content == "hello world"
    assert result.model == "gemma3:4b"


def test_validate_setup_requires_master_key() -> None:
    settings = _settings()
    settings = Settings(
        repo_root=settings.repo_root,
        config_dir=settings.config_dir,
        env_file=settings.env_file,
        compose_file=settings.compose_file,
        virtual_key_file=settings.virtual_key_file,
        ollama_model=settings.ollama_model,
        ollama_host=settings.ollama_host,
        litellm_port=settings.litellm_port,
        litellm_master_key="",
        litellm_ollama_model=settings.litellm_ollama_model,
        litellm_model_name=settings.litellm_model_name,
    )
    with pytest.raises(RuntimeError, match="LITELLM_MASTER_KEY"):
        validate_setup(settings)


def test_validate_setup_rejects_invalid_choices_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings()

    monkeypatch.setattr(
        "local_llm_proxy.services.validate.requests.get",
        lambda *args, **kwargs: DummyResponse({}),
    )
    monkeypatch.setattr(
        "local_llm_proxy.services.validate.requests.post",
        lambda *args, **kwargs: DummyResponse({"choices": []}),
    )

    with pytest.raises(RuntimeError, match="Full response"):
        validate_setup(settings)


def test_normalize_ping_host_only_rewrites_hostname() -> None:
    assert (
        _normalize_ping_host("http://" + "host" + ".docker.internal:11434/api/tags?q=1")
        == "http://localhost:11434/api/tags?q=1"
    )
    assert _normalize_ping_host("http://api-ollama.example:11434") == "http://api-ollama.example:11434"
    assert _normalize_ping_host("http://ollama:11434") == "http://localhost:11434"
