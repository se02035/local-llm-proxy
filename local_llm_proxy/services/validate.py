from __future__ import annotations

from dataclasses import dataclass

import requests

from local_llm_proxy.config import Settings
from local_llm_proxy.logging_utils import log
from local_llm_proxy.services.process_utils import command_exists


@dataclass(frozen=True)
class ValidationResult:
    content: str
    model: str


def _normalize_ping_host(ollama_host: str) -> str:
    if "host.docker.internal" in ollama_host:
        return ollama_host.replace("host.docker.internal", "localhost")
    if "ollama" in ollama_host:
        return ollama_host.replace("ollama", "localhost")
    return ollama_host


def validate_setup(settings: Settings) -> ValidationResult:
    if not settings.litellm_master_key:
        raise RuntimeError(
            "LITELLM_MASTER_KEY is not set or is empty. Set it in src/config/.env and retry."
        )
    if not command_exists("curl"):
        raise RuntimeError("curl is required to send HTTP requests.")
    if not command_exists("jq"):
        raise RuntimeError("jq is required to parse JSON.")

    ping_host = _normalize_ping_host(settings.ollama_host)
    model = settings.ollama_model

    log(f"1. Checking Ollama instance at {ping_host} (model: {model})...")
    try:
        resp = requests.get(f"{ping_host}/api/tags", timeout=(5, 10))
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(f"Ollama is not reachable at {ping_host}.") from exc
    log("Ollama is running.")

    log(
        f"2. Sending chat completion (alias model: {model}.local -> Ollama: {model}) "
        f"to LiteLLM on port {settings.litellm_port}..."
    )
    response_body = {
        "model": f"{model}.local",
        "messages": [{"role": "user", "content": "Say 'hello world' and nothing else."}],
    }
    try:
        response = requests.post(
            f"http://localhost:{settings.litellm_port}/v1/chat/completions",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {settings.litellm_master_key}",
            },
            json=response_body,
            timeout=(5, 30),
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(f"Failed to connect to LiteLLM Proxy on port {settings.litellm_port}.") from exc

    payload = response.json()
    content = payload.get("choices", [{}])[0].get("message", {}).get("content")
    if not content:
        raise RuntimeError(f"Failed to get valid response from proxy. Full response: {payload}")

    log(f"Response received successfully: {content}")
    log("Validation passed. Setup is working correctly.")
    return ValidationResult(content=str(content), model=model)
