from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values

_REDACTED_SENTINELS = {"[REDACTED]", "<REDACTED>", "REDACTED"}


@dataclass(frozen=True)
class Settings:
    """Paths and values loaded from `config/.env` at the repository root."""

    repo_root: Path
    config_dir: Path
    env_file: Path
    compose_file: Path
    virtual_key_file: Path
    ollama_model: str
    ollama_host: str
    litellm_port: str
    litellm_master_key: str
    litellm_ollama_model: str
    litellm_model_name: str


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def _normalize_env_value(value: object | None) -> str:
    if value is None:
        return ""
    normalized = str(value).strip()
    if normalized.upper() in _REDACTED_SENTINELS:
        return ""
    return normalized


def load_settings() -> Settings:
    repo_root = _repo_root()
    config_dir = repo_root / "config"
    env_file = config_dir / ".env"
    env_values = dotenv_values(env_file) if env_file.exists() else {}

    ollama_model = _normalize_env_value(env_values.get("OLLAMA_MODEL")) or "gemma3:4b"
    ollama_host = (
        _normalize_env_value(env_values.get("OLLAMA_HOST"))
        or "http://host.docker.internal:11434"  # pragma: allowlist secret
    )
    litellm_port = _normalize_env_value(env_values.get("LITELLM_PORT")) or "4000"
    litellm_master_key = _normalize_env_value(env_values.get("LITELLM_MASTER_KEY"))
    litellm_ollama_model = (
        _normalize_env_value(env_values.get("LITELLM_OLLAMA_MODEL"))
        or f"ollama/{ollama_model}"
    )
    litellm_model_name = (
        _normalize_env_value(env_values.get("LITELLM_MODEL_NAME"))
        or f"{litellm_ollama_model}.ollama"
    )

    return Settings(
        repo_root=repo_root,
        config_dir=config_dir,
        env_file=env_file,
        compose_file=config_dir / "docker-compose.yml",
        virtual_key_file=config_dir / ".litellm_virtual_key",
        ollama_model=ollama_model,
        ollama_host=ollama_host,
        litellm_port=litellm_port,
        litellm_master_key=litellm_master_key,
        litellm_ollama_model=litellm_ollama_model,
        litellm_model_name=litellm_model_name,
    )
