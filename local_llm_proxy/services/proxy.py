from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import requests

from local_llm_proxy.config import Settings
from local_llm_proxy.logging_utils import log
from local_llm_proxy.services.process_utils import run_command


def start_proxy(settings: Settings, *, timeout_seconds: int = 30) -> dict[str, str]:
    """Start docker services and return discovered connection details."""
    log("Starting LiteLLM Proxy and Ngrok tunnel...")
    run_command(
        [
            "docker",
            "compose",
            "-f",
            str(settings.compose_file),
            "--env-file",
            str(settings.env_file),
            "up",
            "-d",
        ],
        error_prefix="Failed to start docker compose services",
    )
    _wait_for_readiness(port=settings.litellm_port, timeout_seconds=timeout_seconds)
    virtual_key = _seed_virtual_key(settings)
    public_url = _wait_for_ngrok_url(timeout_seconds=10)
    log(f"Success! Public Ngrok URL: {public_url}")
    return {"public_url": public_url, "virtual_key": virtual_key}


def stop_proxy(settings: Settings) -> None:
    """Stop docker services."""
    log("Stopping LiteLLM Proxy and Ngrok tunnel...")
    run_command(
        [
            "docker",
            "compose",
            "-f",
            str(settings.compose_file),
            "--env-file",
            str(settings.env_file),
            "down",
            "--remove-orphans",
        ],
        error_prefix="Failed to stop docker compose services",
    )
    log("Teardown complete.")


def restart_proxy(settings: Settings, *, timeout_seconds: int = 30) -> dict[str, str]:
    """Restart docker services."""
    stop_proxy(settings)
    return start_proxy(settings, timeout_seconds=timeout_seconds)


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
        return settings.virtual_key_file.read_text(encoding="utf-8").strip()

    headers = {"Authorization": f"Bearer {settings.litellm_master_key}"}
    models_response = requests.get("http://localhost:4000/v1/models", headers=headers, timeout=5)
    models_response.raise_for_status()
    model_ids = [
        item.get("id")
        for item in models_response.json().get("data", [])
        if item.get("id")
    ]
    payload = {"models": model_ids, "key_alias": "local-proxy-key"}
    key_response = requests.post(
        "http://localhost:4000/key/generate",
        headers={**headers, "Content-Type": "application/json"},
        json=payload,
        timeout=5,
    )
    key_response.raise_for_status()
    virtual_key = key_response.json().get("key")
    if not virtual_key:
        raise RuntimeError("Failed to generate LiteLLM virtual key.")
    _write_virtual_key(settings.virtual_key_file, str(virtual_key))
    return str(virtual_key)


def _write_virtual_key(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{value}\n", encoding="utf-8")
