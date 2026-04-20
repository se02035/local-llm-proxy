from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values


@dataclass(frozen=True)
class Settings:
    script_dir: Path
    config_dir: Path
    env_file: Path
    compose_file: Path
    virtual_key_file: Path
    ollama_model: str
    ollama_host: str
    litellm_port: str
    litellm_master_key: str


def _script_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "src"


def load_settings() -> Settings:
    script_dir = _script_dir()
    config_dir = script_dir / "config"
    env_file = config_dir / ".env"
    env_values = dotenv_values(env_file) if env_file.exists() else {}

    return Settings(
        script_dir=script_dir,
        config_dir=config_dir,
        env_file=env_file,
        compose_file=config_dir / "docker-compose.yml",
        virtual_key_file=config_dir / ".litellm_virtual_key",
        ollama_model=str(env_values.get("OLLAMA_MODEL", "gemma3:12b")),
        ollama_host=str(env_values.get("OLLAMA_HOST", "http://localhost:11434")),
        litellm_port=str(env_values.get("LITELLM_PORT", "4000")),
        litellm_master_key=str(env_values.get("LITELLM_MASTER_KEY", "")),
    )
