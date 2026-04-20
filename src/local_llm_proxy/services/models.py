"""Model management commands for Ollama."""

from __future__ import annotations

from local_llm_proxy.logging_utils import log
from local_llm_proxy.services.process_utils import run_command


def add_model(model: str) -> None:
    """Pull an Ollama model."""
    log(f"Pulling model: {model}")
    run_command(["ollama", "pull", model], error_prefix=f"Failed to pull model {model}")
    log(f"Model {model} pulled successfully.")


def remove_model(model: str) -> None:
    """Remove an Ollama model."""
    log(f"Removing model: {model}")
    run_command(["ollama", "rm", model], error_prefix=f"Failed to remove model {model}")
    log(f"Model {model} removed successfully.")


def list_models() -> None:
    """List locally available Ollama models."""
    run_command(["ollama", "list"], error_prefix="Failed to list models")
