"""Broker interface definitions used by the execution layer."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class AccountSnapshot:
    """Minimal account state required for order generation and risk checks."""

    equity: float
    cash: float


@dataclass(frozen=True)
class Position:
    """Current broker position represented in shares."""

    symbol: str
    qty: float
    market_value: float = 0.0


@dataclass(frozen=True)
class PlannedOrder:
    """Order instruction produced before broker submission."""

    symbol: str
    side: str
    qty: int
    estimated_price: float
    estimated_notional: float


class BrokerBase(ABC):
    """Abstract broker contract for paper/live execution adapters."""

    @abstractmethod
    def get_account(self) -> AccountSnapshot:
        """Return current account equity and cash."""

    @abstractmethod
    def get_positions(self) -> dict[str, Position]:
        """Return current positions keyed by symbol."""

    @abstractmethod
    def submit_order(self, order: PlannedOrder) -> object:
        """Submit one planned order and return broker response."""
