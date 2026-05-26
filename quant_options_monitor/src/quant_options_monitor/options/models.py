"""Pydantic models for options chains, legs, and strategy candidates."""

from __future__ import annotations

from datetime import date, datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator


class OptionType(str, Enum):
    CALL = "call"
    PUT = "put"


class LegAction(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OptionContract(BaseModel):
    """Normalized option contract data."""

    model_config = ConfigDict(use_enum_values=True)

    symbol: str
    underlying_symbol: str
    expiration: date
    strike: float = Field(gt=0)
    option_type: OptionType
    bid: float = Field(default=0.0, ge=0)
    ask: float = Field(default=0.0, ge=0)
    last: float = Field(default=0.0, ge=0)
    volume: int = Field(default=0, ge=0)
    open_interest: int = Field(default=0, ge=0)
    implied_volatility: Optional[float] = Field(default=None, ge=0)
    delta: Optional[float] = None
    gamma: Optional[float] = None
    theta: Optional[float] = None
    vega: Optional[float] = None

    @field_validator("symbol", "underlying_symbol")
    @classmethod
    def non_empty_symbol(cls, value: str) -> str:
        value = value.strip().upper()
        if not value:
            raise ValueError("symbol fields must not be empty")
        return value

    @computed_field  # type: ignore[prop-decorator]
    @property
    def mid_price(self) -> float:
        if self.bid > 0 and self.ask > 0:
            return (self.bid + self.ask) / 2
        return self.last

    @computed_field  # type: ignore[prop-decorator]
    @property
    def bid_ask_spread(self) -> float:
        return max(self.ask - self.bid, 0.0)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def bid_ask_spread_pct(self) -> float:
        mid = self.mid_price
        if mid <= 0:
            return 1.0
        return self.bid_ask_spread / mid

    @computed_field  # type: ignore[prop-decorator]
    @property
    def dte(self) -> int:
        return max((self.expiration - datetime.now(timezone.utc).date()).days, 0)


class OptionChain(BaseModel):
    """Options chain snapshot for one underlying."""

    model_config = ConfigDict(use_enum_values=True)

    underlying_symbol: str
    underlying_price: float = Field(gt=0)
    as_of: datetime
    contracts: list[OptionContract] = Field(default_factory=list)

    @field_validator("underlying_symbol")
    @classmethod
    def normalize_underlying_symbol(cls, value: str) -> str:
        value = value.strip().upper()
        if not value:
            raise ValueError("underlying_symbol must not be empty")
        return value


class OptionLeg(BaseModel):
    """One leg in a multi-leg option strategy."""

    model_config = ConfigDict(use_enum_values=True)

    action: LegAction
    option: OptionContract
    quantity: int = Field(gt=0)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def signed_quantity(self) -> int:
        return self.quantity if self.action == LegAction.BUY.value else -self.quantity

    @computed_field  # type: ignore[prop-decorator]
    @property
    def estimated_premium(self) -> float:
        premium = self.option.mid_price * self.quantity * 100
        return -premium if self.action == LegAction.BUY.value else premium


class OptionStrategyCandidate(BaseModel):
    """Alert-ready candidate for a multi-leg option strategy."""

    model_config = ConfigDict(use_enum_values=True)

    strategy_name: str
    underlying_symbol: str
    legs: list[OptionLeg] = Field(min_length=1)
    max_loss: Optional[float] = Field(default=None, ge=0)
    max_profit: Optional[float] = Field(default=None, ge=0)
    breakevens: list[float] = Field(default_factory=list)
    estimated_debit_or_credit: float
    score: float = 0.0
    reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @field_validator("strategy_name", "underlying_symbol")
    @classmethod
    def non_empty_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("text fields must not be empty")
        return value.upper() if value.isalpha() else value

    def as_alert_dict(self) -> dict[str, object]:
        """Return a compact dictionary suitable for console/email/Telegram alerts."""

        return self.model_dump(
            mode="json",
            exclude_none=True,
        )
