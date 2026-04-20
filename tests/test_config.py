from __future__ import annotations

from local_llm_proxy import config


def test_normalize_env_value_handles_redacted_sentinels() -> None:
    assert config._normalize_env_value("[REDACTED]") == ""
    assert config._normalize_env_value("<REDACTED>") == ""
    assert config._normalize_env_value("REDACTED") == ""
    assert config._normalize_env_value("  real-value  ") == "real-value"


def test_repo_root_finds_repository_marker() -> None:
    root = config._repo_root()
    assert (root / "pyproject.toml").exists()
