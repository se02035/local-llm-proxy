from __future__ import annotations

from pathlib import Path

import click

from local_llm_proxy.config import load_settings
from local_llm_proxy.logging_utils import err
from local_llm_proxy.services.models import add_model, list_models, remove_model
from local_llm_proxy.services.proxy import restart_proxy, start_proxy, stop_proxy
from local_llm_proxy.services.validate import validate_setup


@click.group(help="Manage local LiteLLM proxy and Ollama models.")
def cli() -> None:
    """Top-level CLI group."""


@cli.group(help="Manage proxy lifecycle.")
def setup() -> None:
    """Setup command group."""


@setup.command("start")
@click.option(
    "--litellm-config",
    "litellm_config_file",
    type=click.Path(path_type=Path),
    default=Path("config/litellm-config.yaml"),
    show_default=True,
    help="Path to LiteLLM config YAML used by the proxy container.",
)
def setup_start(litellm_config_file: Path) -> None:
    """Start proxy services."""
    settings = load_settings()
    config_path = litellm_config_file
    if not config_path.is_absolute():
        config_path = settings.repo_root / config_path
    if not config_path.exists():
        raise click.ClickException(f"LiteLLM config file not found: {config_path}")
    try:
        result = start_proxy(settings, litellm_config_file=config_path)
    except RuntimeError as exc:
        err(str(exc))
        raise click.ClickException(str(exc)) from exc
    click.echo(f"Public ngrok URL: {result['public_url']}")
    click.echo(f"Virtual key: {result['virtual_key']}")


@setup.command("stop")
def setup_stop() -> None:
    """Stop proxy services."""
    settings = load_settings()
    stop_proxy(settings)
    click.echo("Teardown complete.")


@setup.command("restart")
def setup_restart() -> None:
    """Restart proxy services."""
    settings = load_settings()
    try:
        result = restart_proxy(settings)
    except RuntimeError as exc:
        err(str(exc))
        raise click.ClickException(str(exc)) from exc
    click.echo(f"Public ngrok URL: {result['public_url']}")
    click.echo(f"Virtual key: {result['virtual_key']}")


@cli.group(help="Manage local Ollama models.")
def models() -> None:
    """Model management command group."""


@models.command("add")
@click.argument("model")
def models_add(model: str) -> None:
    """Pull model into local Ollama."""
    add_model(model)


@models.command("remove")
@click.argument("model")
def models_remove(model: str) -> None:
    """Remove model from local Ollama."""
    remove_model(model)


@models.command("list")
def models_list() -> None:
    """List local Ollama models."""
    list_models()


@cli.command("validate")
def cli_validate() -> None:
    """Validate end-to-end setup."""
    settings = load_settings()
    try:
        result = validate_setup(settings)
    except RuntimeError as exc:
        err(str(exc))
        raise click.ClickException(str(exc)) from exc
    click.echo(f"Validation response: {result.content}")
