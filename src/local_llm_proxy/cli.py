from __future__ import annotations

from pathlib import Path

import click

from local_llm_proxy.config import load_settings
from local_llm_proxy.logging_utils import err
from local_llm_proxy.services.models import add_model, list_models, remove_model
from local_llm_proxy.services.proxy import get_proxy_status, restart_proxy, start_proxy, stop_proxy
from local_llm_proxy.services.validate import validate_setup


def _render_table(rows: list[tuple[str, str]]) -> str:
    header = ("Field", "Value")
    normalized_rows = [(key, value) for key, value in rows]

    key_width = max(len(header[0]), *(len(key) for key, _ in normalized_rows))
    value_width = max(len(header[1]), *(len(value) for _, value in normalized_rows))

    divider = f"+-{'-' * key_width}-+-{'-' * value_width}-+"
    lines = [
        divider,
        f"| {header[0].ljust(key_width)} | {header[1].ljust(value_width)} |",
        divider,
    ]
    lines.extend(
        f"| {key.ljust(key_width)} | {value.ljust(value_width)} |"
        for key, value in normalized_rows
    )
    lines.append(divider)
    return "\n".join(lines)


def _render_grouped_tables(groups: list[tuple[str, list[tuple[str, str]]]]) -> str:
    blocks: list[str] = []
    for title, rows in groups:
        if not rows:
            continue
        blocks.append(f"{title}")
        blocks.append(_render_table(rows))
    return "\n\n".join(blocks)


def _build_status_groups(
    *, settings, public_url: str, ngrok_admin_url: str | None, virtual_key: str
) -> list[tuple[str, list[tuple[str, str]]]]:
    local_endpoint = f"http://localhost:{settings.litellm_port}"
    ngrok_rows: list[tuple[str, str]] = []
    if ngrok_admin_url:
        ngrok_rows.append(("Ngrok admin URL", ngrok_admin_url))
    if public_url:
        ngrok_rows.append(("Public ngrok URL", public_url))

    litellm_rows = [
        ("LiteLLM local endpoint", local_endpoint),
        ("LiteLLM local admin URL", f"{local_endpoint}/ui/"),
    ]
    if public_url:
        litellm_rows.append(("LiteLLM public admin URL", f"{public_url.rstrip('/')}/ui/"))
    litellm_rows.append(("Virtual key", virtual_key or "(not found)"))

    return [("Ngrok", ngrok_rows), ("LiteLLM", litellm_rows)]


@click.group(help="Manage local LiteLLM proxy and Ollama models.")
def cli() -> None:
    """Top-level CLI group.

    Args:
        None.

    Returns:
        None: Registered as a Click command group entrypoint.
    """


@cli.group(help="Manage proxy lifecycle.")
def setup() -> None:
    """Setup command group.

    Args:
        None.

    Returns:
        None: Registered as a Click subgroup.
    """


@setup.command("start")
@click.option(
    "--litellm-config",
    "litellm_config_file",
    type=click.Path(path_type=Path),
    default=Path("config/litellm-config.yaml"),
    show_default=True,
    help="Path to LiteLLM config YAML used by the proxy container.",
)
@click.option(
    "--public",
    is_flag=True,
    default=False,
    help="Expose LiteLLM through ngrok public tunnel.",
)
def setup_start(litellm_config_file: Path, public: bool) -> None:
    """Start proxy services.

    Args:
        litellm_config_file: Relative or absolute path to LiteLLM config YAML.
        public: Whether to expose the proxy through ngrok.

    Returns:
        None: Writes endpoint and key details to the terminal.
    """
    settings = load_settings()
    config_path = litellm_config_file
    if not config_path.is_absolute():
        config_path = settings.repo_root / config_path
    if not config_path.exists():
        raise click.ClickException(f"LiteLLM config file not found: {config_path}")
    try:
        result = start_proxy(settings, litellm_config_file=config_path, public=public)
    except RuntimeError as exc:
        err(f"Failed to start proxy: {exc}")
        raise click.ClickException(f"Failed to start proxy: {exc}") from exc

    groups = _build_status_groups(
        settings=settings,
        public_url=result["public_url"] if public else "",
        ngrok_admin_url="http://localhost:4040" if public else None,
        virtual_key=result["virtual_key"],
    )
    click.echo(_render_grouped_tables(groups))


@setup.command("stop")
def setup_stop() -> None:
    """Stop proxy services.

    Args:
        None.

    Returns:
        None: Writes teardown status to the terminal.
    """
    settings = load_settings()
    try:
        stop_proxy(settings)
    except RuntimeError as exc:
        err(str(exc))
        raise click.ClickException(str(exc)) from exc
    click.echo("Teardown complete.")


@setup.command("status")
def setup_status() -> None:
    """Print status URLs and credentials for the active setup.

    Args:
        None.

    Returns:
        None: Writes available local/public URLs and virtual key status.
    """
    settings = load_settings()
    status = get_proxy_status(settings)

    ngrok_rows: list[tuple[str, str]] = [("Ngrok admin URL", status["ngrok_admin_url"])]
    if status["public_url"]:
        ngrok_rows.append(("Public ngrok URL", status["public_url"]))

    litellm_rows: list[tuple[str, str]] = [
        ("LiteLLM local endpoint", status["local_endpoint"]),
        ("LiteLLM local admin URL", status["local_admin_url"]),
    ]
    if status["public_url"]:
        litellm_rows.append(("LiteLLM public admin URL", f"{status['public_url'].rstrip('/')}/ui/"))
    litellm_rows.append(("Virtual key", status["virtual_key"] or "(not found)"))

    click.echo(_render_grouped_tables([("Ngrok", ngrok_rows), ("LiteLLM", litellm_rows)]))


@setup.command("restart")
@click.option(
    "--public",
    is_flag=True,
    default=False,
    help="Expose LiteLLM through ngrok public tunnel.",
)
def setup_restart(public: bool) -> None:
    """Restart proxy services.

    Args:
        public: Whether to expose the proxy through ngrok.

    Returns:
        None: Writes endpoint and key details to the terminal.
    """
    settings = load_settings()
    try:
        result = restart_proxy(settings, public=public)
    except RuntimeError as exc:
        err(str(exc))
        raise click.ClickException(str(exc)) from exc
    groups = _build_status_groups(
        settings=settings,
        public_url=result["public_url"],
        ngrok_admin_url="http://localhost:4040" if result["public_url"] else None,
        virtual_key=result["virtual_key"],
    )
    click.echo(_render_grouped_tables(groups))


@cli.group(help="Manage local Ollama models.")
def models() -> None:
    """Model management command group.

    Args:
        None.

    Returns:
        None: Registered as a Click subgroup.
    """


@models.command("add")
@click.argument("model")
def models_add(model: str) -> None:
    """Pull model into local Ollama.

    Args:
        model: Ollama model identifier to pull locally.

    Returns:
        None: Writes progress to the terminal.
    """
    add_model(model)


@models.command("remove")
@click.argument("model")
def models_remove(model: str) -> None:
    """Remove model from local Ollama.

    Args:
        model: Ollama model identifier to remove.

    Returns:
        None: Writes progress to the terminal.
    """
    remove_model(model)


@models.command("list")
def models_list() -> None:
    """List local Ollama models.

    Args:
        None.

    Returns:
        None: Writes model listing to the terminal.
    """
    list_models()


@cli.command("validate")
def cli_validate() -> None:
    """Validate end-to-end setup.

    Args:
        None.

    Returns:
        None: Writes validation response content to the terminal.
    """
    settings = load_settings()
    try:
        result = validate_setup(settings)
    except RuntimeError as exc:
        err(str(exc))
        raise click.ClickException(str(exc)) from exc
    click.echo(f"Validation response: {result.content}")
