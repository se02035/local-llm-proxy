from __future__ import annotations

import os
import subprocess
from collections.abc import Mapping
from shutil import which

from local_llm_proxy.logging_utils import trace


def _format_runtime_error(error_prefix: str | None, detail: str) -> RuntimeError:
    if error_prefix:
        return RuntimeError(f"{error_prefix}: {detail}".strip())
    return RuntimeError(detail)


def run_command(
    command: list[str],
    *,
    capture_output: bool = False,
    error_prefix: str | None = None,
    env: Mapping[str, str] | None = None,
    timeout: float | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a subprocess command and normalize common failures.

    Args:
        command: Command tokens to execute.
        capture_output: Whether to capture stdout/stderr on completion.
        error_prefix: Optional prefix prepended to raised runtime errors.
        env: Optional environment variables merged with the current process env.
        timeout: Optional timeout for the subprocess command.

    Returns:
        subprocess.CompletedProcess[str]: Completed subprocess result object.
    """
    merged_env = None if env is None else {**os.environ, **env}
    trace(
        "Executing command",
        command=command,
        capture_output=capture_output,
        has_env_overrides=env is not None,
    )
    try:
        result = subprocess.run(
            command,
            check=True,
            text=True,
            capture_output=capture_output,
            env=merged_env,
            timeout=timeout,
        )
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or str(exc)).strip()
        trace("Command failed", command=command, return_code=exc.returncode, detail=detail)
        raise _format_runtime_error(error_prefix, detail) from exc
    except FileNotFoundError as exc:
        detail = f"Command not found: {command[0]}"
        trace("Command binary not found", command=command, detail=detail)
        raise _format_runtime_error(error_prefix, detail) from exc
    except subprocess.TimeoutExpired as exc:
        detail = f"Command timed out: {' '.join(command)}"
        trace("Command timed out", command=command, detail=detail)
        raise _format_runtime_error(error_prefix, detail) from exc
    trace("Command completed", command=command, return_code=result.returncode)
    return result


def command_exists(name: str) -> bool:
    """Check whether a command is available on PATH.

    Args:
        name: Command name to look up.

    Returns:
        bool: True when the command can be resolved, otherwise False.
    """
    return which(name) is not None


def output(command: list[str]) -> str:
    """Run a command and return stdout text.

    Args:
        command: Command tokens to execute.

    Returns:
        str: Captured stdout emitted by the command.
    """
    return run_command(command, capture_output=True).stdout
