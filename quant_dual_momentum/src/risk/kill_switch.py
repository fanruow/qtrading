"""Simple file-based kill switch for paper trading runs."""

from __future__ import annotations

from pathlib import Path


def is_kill_switch_active(path: str | Path = "KILL_SWITCH") -> bool:
    """Return True when the kill switch file exists."""
    return Path(path).exists()
