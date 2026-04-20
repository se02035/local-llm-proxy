from __future__ import annotations

import subprocess
from shutil import which


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
        detail = exc.stderr or exc.stdout or str(exc)
        if error_prefix:
            raise RuntimeError(f"{error_prefix}: {detail}".strip()) from exc
        raise RuntimeError(detail.strip()) from exc
    return result


def command_exists(name: str) -> bool:
    return which(name) is not None


def output(command: list[str]) -> str:
    return subprocess.run(
        command,
        check=True,
        text=True,
        capture_output=True,
    ).stdout
