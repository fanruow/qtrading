"""Market data domain models."""

from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, Field


OptionRight = Literal["call", "put"]


class OptionContract(BaseModel):
    symbol: str
    expiration: date
    strike: float
    right: OptionRight
    bid: float = 0.0
    ask: float = 0.0
    last: float = 0.0
    volume: int = 0
    open_interest: int = 0
    implied_volatility: Optional[float] = None
    delta: Optional[float] = None

    @property
    def mid(self) -> float:
        if self.bid > 0 and self.ask > 0:
            return (self.bid + self.ask) / 2
        return self.last

    @property
    def bid_ask_spread_pct(self) -> float:
        mid = self.mid
        if mid <= 0:
            return 1.0
        return max(self.ask - self.bid, 0.0) / mid


class StrategyCandidate(BaseModel):
    symbol: str
    strategy: str
    candidate_strikes: list[float]
    dte: int
    max_loss: Optional[float]
    max_profit: Optional[float]
    breakeven: list[float]
    liquidity_filters: dict[str, bool]
    reason: str
    legs: list[OptionContract] = Field(default_factory=list)
