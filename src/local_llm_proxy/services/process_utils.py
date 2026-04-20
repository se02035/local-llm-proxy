from __future__ import annotations

import subprocess
from shutil import which


def _format_runtime_error(error_prefix: str | None, detail: str) -> RuntimeError:
    if error_prefix:
        return RuntimeError(f"{error_prefix}: {detail}".strip())
    return RuntimeError(detail)


def run_command(
    command: list[str], *, capture_output: bool = False, error_prefix: str | None = None
) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            command,
            check=True,
            text=True,
            capture_output=capture_output,
        )
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or str(exc)).strip()
        raise _format_runtime_error(error_prefix, detail) from exc
    except FileNotFoundError as exc:
        detail = f"Command not found: {command[0]}"
        raise _format_runtime_error(error_prefix, detail) from exc
    except subprocess.TimeoutExpired as exc:
        detail = f"Command timed out: {' '.join(command)}"
        raise _format_runtime_error(error_prefix, detail) from exc
    return result


def command_exists(name: str) -> bool:
    return which(name) is not None


def output(command: list[str]) -> str:
    return run_command(command, capture_output=True).stdout
