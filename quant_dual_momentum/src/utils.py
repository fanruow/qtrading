"""Shared utilities for the backtest project."""

from __future__ import annotations

from pathlib import Path


def ensure_dir(path: str | Path) -> Path:
    """Create a directory if needed and return it as a Path."""
    out = Path(path)
    out.mkdir(parents=True, exist_ok=True)
    return out


def validate_weights(weights_sum: float, tolerance: float = 1e-10) -> None:
    """Raise ValueError if risky-asset weights exceed full capital."""
    if weights_sum > 1.0 + tolerance:
        raise ValueError(f"Weights sum to {weights_sum:.6f}, above 1.0.")
