"""Scheduling helpers for live paper trading commands."""

from __future__ import annotations

import pandas as pd


def should_rebalance_today(frequency: str, today: pd.Timestamp | None = None) -> bool:
    """Return True when a rebalance should run for the configured frequency."""
    if frequency != "monthly":
        raise ValueError(f"Unsupported rebalance_frequency: {frequency}")
    current = (today or pd.Timestamp.today()).normalize()
    next_business_day = current + pd.offsets.BDay(1)
    return current.month != next_business_day.month
