from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

import requests

from local_llm_proxy.config import Settings
from local_llm_proxy.logging_utils import log


@dataclass(frozen=True)
class ValidationResult:
    content: str
    model: str


def _normalize_ping_host(ollama_host: str) -> str:
    """Normalize Ollama ping hosts to localhost while preserving URL components.

    Trims whitespace, supports inputs with or without a scheme, and maps `host.docker.internal`
    and `ollama` hostnames to `localhost` while preserving userinfo, port, path, query, and fragment.
    Returns the rebuilt URL string, removing a leading `//` when the original input had no scheme;
    empty input or missing hostname are returned unchanged.
    """
    host_input = ollama_host.strip()
    if not host_input:
        return host_input

    parsed = urlsplit(host_input)
    has_scheme = bool(parsed.scheme)
    if not has_scheme:
        parsed = urlsplit(f"//{host_input}")

    if not parsed.hostname:
        return host_input

    mapped_host = parsed.hostname
    if mapped_host in {"host.docker.internal", "ollama"}:
        mapped_host = "localhost"

    if mapped_host == parsed.hostname:
        return host_input

    userinfo = ""
    if parsed.username:
        userinfo = parsed.username
        if parsed.password:
            userinfo += f":{parsed.password}"
        userinfo += "@"

    port = f":{parsed.port}" if parsed.port else ""
    netloc = f"{userinfo}{mapped_host}{port}"

    rebuilt = urlunsplit(
        (
            parsed.scheme if has_scheme else "",
            netloc,
            parsed.path,
            parsed.query,
            parsed.fragment,
        )
    )
    if not has_scheme and rebuilt.startswith("//"):
        return rebuilt[2:]
    return rebuilt


def validate_setup(settings: Settings) -> ValidationResult:
    """Validate host Ollama reachability and LiteLLM chat completion flow.

    Args:
        settings: Loaded runtime settings, including hosts, ports, and API keys.

    Returns:
        ValidationResult: Model metadata and generated completion content.
    """
    if not settings.litellm_master_key:
        raise RuntimeError("LITELLM_MASTER_KEY is not set or is empty. Set it in .env and retry.")
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
        f"2. Sending chat completion (alias model: {settings.litellm_model_name}) "
        f"to LiteLLM on port {settings.litellm_port}..."
    )
    response_body = {
        "model": settings.litellm_model_name,
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

    try:
        payload = response.json()
    except ValueError as exc:
        raw_response = getattr(response, "text", None)
        if raw_response is None:
            raw_content = getattr(response, "content", b"")
            if isinstance(raw_content, bytes):
                raw_response = raw_content.decode("utf-8", errors="replace")
            else:
                raw_response = str(raw_content)
        raise RuntimeError(f"Failed to get valid response from proxy. Full response: {raw_response}") from exc

    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise RuntimeError(f"Failed to get valid response from proxy. Full response: {payload}")

    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        raise RuntimeError(f"Failed to get valid response from proxy. Full response: {payload}")

    message = first_choice.get("message")
    if not isinstance(message, dict):
        raise RuntimeError(f"Failed to get valid response from proxy. Full response: {payload}")

    content = message.get("content")
    if not content:
        raise RuntimeError(f"Failed to get valid response from proxy. Full response: {payload}")

    log(f"Response received successfully: {content}")
    log("Validation passed. Setup is working correctly.")
    return ValidationResult(content=str(content), model=model)
