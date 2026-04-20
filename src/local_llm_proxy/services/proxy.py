from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any

import requests

from local_llm_proxy.config import Settings
from local_llm_proxy.logging_utils import log
from local_llm_proxy.services.process_utils import run_command

_COMPOSE_PROJECT_NAME = "local-llm-proxy"


def start_proxy(
    settings: Settings,
    *,
    litellm_config_file: Path | None = None,
    public: bool = False,
    timeout_seconds: int = 30,
) -> dict[str, str]:
    """Start docker services and return discovered connection details.

    Args:
        settings: Loaded settings with compose, env, and proxy metadata.
        litellm_config_file: Optional custom LiteLLM YAML path for container config.
        public: Whether to enable the ngrok public tunnel profile.
        timeout_seconds: Maximum seconds to wait for readiness checks.

    Returns:
        dict[str, str]: Keys `public_url` and `virtual_key` for the active session.
    """
    log("Starting LiteLLM Proxy services...")
    compose_command = _compose_command(settings, public=public)
    command = [*compose_command, "up", "-d"]
    compose_env = None
    if litellm_config_file is not None:
        compose_env = {"LITELLM_CONFIG_FILE": str(litellm_config_file)}
    try:
        run_command(
            command,
            error_prefix="Failed to start docker compose services",
            env=compose_env,
        )
    except RuntimeError as exc:
        diagnostics = _collect_compose_failure_diagnostics(settings, public=public)
        guidance = _compose_failure_guidance(
            error_message=str(exc),
            diagnostics=diagnostics,
            public=public,
        )
        if diagnostics:
            raise RuntimeError(f"{guidance}\n\n{diagnostics}") from exc
        raise RuntimeError(guidance) from exc

    _wait_for_readiness(port=settings.litellm_port, timeout_seconds=timeout_seconds)
    virtual_key = _seed_virtual_key(settings)

    public_url = ""
    if public:
        public_url = _wait_for_ngrok_url(timeout_seconds=10)
        log(f"Success! Public Ngrok URL: {public_url}")
    else:
        log("Success! LiteLLM is available on localhost only (public tunnel disabled).")

    return {"public_url": public_url, "virtual_key": virtual_key}


def stop_proxy(settings: Settings) -> None:
    """Stop docker services.

    Args:
        settings: Loaded settings with compose and env file paths.

    Returns:
        None: This function performs side effects only.
    """
    log("Stopping LiteLLM Proxy services...")
    # Include profiled services so `setup stop` always removes ngrok when present.
    compose_command = _compose_command(settings, public=True)
    run_command(
        [*compose_command, "down", "--remove-orphans"],
        error_prefix="Failed to stop docker compose services",
    )
    log("Teardown complete.")


def restart_proxy(
    settings: Settings,
    *,
    litellm_config_file: Path | None = None,
    public: bool = False,
    timeout_seconds: int = 30,
) -> dict[str, str]:
    """Restart docker services.

    Args:
        settings: Loaded settings with compose, env, and proxy metadata.
        litellm_config_file: Optional custom LiteLLM YAML path for container config.
        public: Whether to enable the ngrok public tunnel profile.
        timeout_seconds: Maximum seconds to wait for readiness checks.

    Returns:
        dict[str, str]: Keys `public_url` and `virtual_key` for the restarted session.
    """
    stop_proxy(settings)
    return start_proxy(
        settings,
        litellm_config_file=litellm_config_file,
        public=public,
        timeout_seconds=timeout_seconds,
    )


def get_proxy_status(settings: Settings) -> dict[str, str | bool]:
    """Return user-facing status details for the current proxy setup.

    Args:
        settings: Loaded settings with file paths and port configuration.

    Returns:
        dict[str, str | bool]: Running-state flags plus URLs and cached virtual key.
    """
    running_services = _running_compose_services(settings)
    local_endpoint = f"http://localhost:{settings.litellm_port}"
    status = {
        "local_endpoint": "",
        "local_admin_url": "",
        "ngrok_admin_url": "",
        "public_url": "",
        "virtual_key": "",
        "litellm_running": "litellm" in running_services,
        "ngrok_running": "ngrok" in running_services,
    }

    if status["litellm_running"]:
        status["local_endpoint"] = local_endpoint
        status["local_admin_url"] = f"{local_endpoint}/ui/"
    if status["litellm_running"] and settings.virtual_key_file.exists():
        status["virtual_key"] = settings.virtual_key_file.read_text(encoding="utf-8").strip()

    if status["ngrok_running"]:
        status["ngrok_admin_url"] = "http://localhost:4040"
        try:
            response = requests.get("http://localhost:4040/api/tunnels", timeout=1)
            if response.ok:
                data = response.json()
                tunnels: list[dict[str, Any]] = data.get("tunnels", [])
                if tunnels:
                    public_url = tunnels[0].get("public_url")
                    if public_url:
                        status["public_url"] = str(public_url)
        except (requests.RequestException, ValueError, TypeError, json.JSONDecodeError):
            pass

    return status


def _running_compose_services(settings: Settings) -> set[str]:
    """Return compose service names that are currently running.

    Args:
        settings: Loaded settings with compose file and env file paths.

    Returns:
        set[str]: Running service names in the local compose project.
    """
    try:
        result = run_command(
            [*_compose_command(settings, public=True), "ps", "--services", "--filter", "status=running"],
            capture_output=True,
        )
    except RuntimeError:
        return set()

    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def _compose_command(settings: Settings, *, public: bool) -> list[str]:
    command = [
        "docker",
        "compose",
        "-p",
        _COMPOSE_PROJECT_NAME,
        "-f",
        str(settings.compose_file),
    ]
    if settings.env_file.is_file():
        command.extend(["--env-file", str(settings.env_file)])
    if public:
        command.extend(["--profile", "public"])
    return command


def _collect_compose_failure_diagnostics(settings: Settings, *, public: bool) -> str:
    diagnostics: list[str] = []
    compose_command = _compose_command(settings, public=public)
    diagnostic_commands: list[tuple[str, list[str]]] = [
        ("docker compose ps --all", ["ps", "--all"]),
        ("docker compose logs --no-color --tail 120", ["logs", "--no-color", "--tail", "120"]),
    ]

    for label, args in diagnostic_commands:
        try:
            result = run_command([*compose_command, *args], capture_output=True)
        except RuntimeError as exc:
            diagnostics.append(f"{label}: unavailable ({exc})")
            continue

        detail = ((result.stdout or "").strip() or (result.stderr or "").strip()).strip()
        if detail:
            diagnostics.append(f"{label}:\n{detail}")

    if not diagnostics:
        return ""
    return "Additional docker compose diagnostics:\n\n" + "\n\n".join(diagnostics)


def _compose_failure_guidance(*, error_message: str, diagnostics: str, public: bool) -> str:
    combined = f"{error_message}\n{diagnostics}".lower()
    suggestions: list[str] = []

    if "cannot connect to the docker daemon" in combined or "is the docker daemon running" in combined:
        suggestions.append("Docker daemon is not reachable. Start Docker Desktop (or the daemon) and retry.")
    if "port is already allocated" in combined or "address already in use" in combined:
        suggestions.append(
            "A required port is already in use. Free the conflicting port or change `LITELLM_PORT` in `.env`."
        )
    if "invalid mount config" in combined or "bind source path does not exist" in combined:
        suggestions.append(
            "The configured LiteLLM config file path is invalid. Verify `--litellm-config` points to an existing file."
        )
    if "litellm-proxy is unhealthy" in combined or "litellm-proxy unhealthy" in combined:
        suggestions.append(
            "Container `litellm-proxy` became unhealthy. Check env values in `.env` "
            "(especially `OLLAMA_HOST`, model aliases, and `LITELLM_MASTER_KEY`)."
        )
    if "ngrok" in combined and ("authtoken" in combined or "authentication failed" in combined):
        suggestions.append(
            "`ngrok` failed authentication. Set a valid `NGROK_AUTHTOKEN` in `.env` before using `--public`."
        )
    if "pull access denied" in combined or "manifest unknown" in combined:
        suggestions.append(
            "Docker image pull failed. Check your network connectivity and confirm image names are valid."
        )

    if not suggestions:
        suggestions.append(
            "Run `docker compose -p local-llm-proxy -f config/docker-compose.yml "
            "--env-file .env ps --all` and inspect the unhealthy/exited service."
        )
        suggestions.append(
            "Run `docker compose -p local-llm-proxy -f config/docker-compose.yml "
            "--env-file .env logs --no-color --tail 120` to view startup failures."
        )
        if public:
            suggestions.append(
                "If using `--public`, verify `NGROK_AUTHTOKEN` is set correctly and that port 4040 is available."
            )

    bullets = "\n".join(f"- {item}" for item in suggestions)
    return (
        f"Failed to start docker compose services.\nActionable next steps:\n{bullets}\nOriginal error: {error_message}"
    )


def _wait_for_readiness(*, port: str, timeout_seconds: int) -> None:
    for _ in range(timeout_seconds):
        try:
            resp = requests.get(f"http://localhost:{port}/health/readiness", timeout=1)
            if resp.ok:
                return
        except requests.RequestException:
            pass
        time.sleep(1)
    raise RuntimeError("LiteLLM proxy failed to become healthy within timeout.")


def _wait_for_ngrok_url(*, timeout_seconds: int) -> str:
    for _ in range(timeout_seconds):
        try:
            resp = requests.get("http://localhost:4040/api/tunnels", timeout=1)
            if not resp.ok:
                time.sleep(1)
                continue
            data = resp.json()
            tunnels: list[dict[str, Any]] = data.get("tunnels", [])
            if tunnels:
                public_url = tunnels[0].get("public_url")
                if public_url:
                    return str(public_url)
        except (requests.RequestException, ValueError, json.JSONDecodeError):
            pass
        time.sleep(1)
    raise RuntimeError("Unable to retrieve ngrok public URL within timeout.")


def _seed_virtual_key(settings: Settings) -> str:
    if not settings.litellm_master_key:
        return ""
    if settings.virtual_key_file.exists():
        cached_key = settings.virtual_key_file.read_text(encoding="utf-8").strip()
        if cached_key and _is_virtual_key_valid(settings, cached_key):
            return cached_key

    headers = {"Authorization": f"Bearer {settings.litellm_master_key}"}
    base = f"http://localhost:{settings.litellm_port}"

    try:
        models_response = requests.get(f"{base}/v1/models", headers=headers, timeout=5)
        models_response.raise_for_status()
        model_ids = [item.get("id") for item in models_response.json().get("data", []) if item.get("id")]

        payload = {"models": model_ids, "key_alias": "local-proxy-key"}
        key_response = requests.post(
            f"{base}/key/generate",
            headers={**headers, "Content-Type": "application/json"},
            json=payload,
            timeout=5,
        )
        key_response.raise_for_status()

        virtual_key = key_response.json().get("key")
    except (requests.RequestException, ValueError, TypeError, KeyError) as exc:
        raise RuntimeError(f"Failed to seed LiteLLM virtual key on port {settings.litellm_port}: {exc}") from exc

    if not virtual_key:
        raise RuntimeError("Failed to generate LiteLLM virtual key.")
    _write_virtual_key(settings.virtual_key_file, str(virtual_key))
    return str(virtual_key)


def _is_virtual_key_valid(settings: Settings, key: str) -> bool:
    base = f"http://localhost:{settings.litellm_port}"
    try:
        response = requests.get(
            f"{base}/v1/models",
            headers={"Authorization": f"Bearer {key}"},
            timeout=5,
        )
        return response.ok
    except requests.RequestException:
        return False


def _write_virtual_key(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as tmp_file:
            tmp_file.write(f"{value}\n")
            tmp_file.flush()
            os.fsync(tmp_file.fileno())

        os.chmod(tmp_path, 0o600)
        os.replace(tmp_path, path)
        path.chmod(0o600)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
