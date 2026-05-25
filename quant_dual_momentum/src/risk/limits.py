"""Configuration models for live paper trading risk limits."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

try:
    from pydantic import field_validator
except ImportError:  # pragma: no cover - pydantic v1 compatibility
    from pydantic import validator as field_validator


class LiveConfig(BaseModel):
    """Validated live paper trading configuration."""

    symbols: list[str]
    target_vol: float = 0.10
    top_n: int = 3
    vol_window: int = 63
    max_position_weight: float = 0.35
    max_order_notional: float = 25_000.0
    min_order_notional: float = 1.0
    max_total_gross_exposure: float = 1.0
    max_daily_turnover: float = 1.0
    max_daily_loss: float = 0.05
    dry_run: bool = True
    paper: bool = True
    rebalance_frequency: Literal["monthly"] = "monthly"
    start: str = "2007-01-01"
    outputs_dir: str = "outputs"
    logs_dir: str = "logs"

    @field_validator("symbols")
    @classmethod
    def symbols_must_not_be_empty(cls, value: list[str]) -> list[str]:
        """Require at least one symbol."""
        if not value:
            raise ValueError("symbols must not be empty")
        return value


def require_paper_trading(paper: bool) -> None:
    """Raise if live trading was requested."""
    if not paper:
        raise ValueError("paper=False is not allowed. This project only supports Alpaca paper trading.")
