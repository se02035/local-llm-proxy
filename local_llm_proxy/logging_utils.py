"""Simple logging helpers for CLI output consistency."""

from __future__ import annotations

from datetime import datetime, timezone

import click


def _timestamp() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%dT%H:%M:%S%z")


def log(message: str) -> None:
    click.echo(f"[INFO] {_timestamp()}: {message}")


def err(message: str) -> None:
    click.echo(f"[ERROR] {_timestamp()}: {message}", err=True)
