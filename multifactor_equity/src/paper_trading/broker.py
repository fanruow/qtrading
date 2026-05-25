from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Account:
    equity: float
    cash: float


@dataclass(frozen=True)
class Position:
    symbol: str
    market_value: float


@dataclass(frozen=True)
class OrderRequest:
    symbol: str
    side: str
    notional: float
    type: str = "market"
    time_in_force: str = "day"


class BrokerInterface(ABC):
    @abstractmethod
    def get_account(self) -> Account:
        raise NotImplementedError

    @abstractmethod
    def get_positions(self) -> list[Position]:
        raise NotImplementedError

    @abstractmethod
    def get_tradable_symbols(self) -> set[str]:
        raise NotImplementedError

    @abstractmethod
    def submit_order(self, order: OrderRequest) -> dict[str, Any]:
        raise NotImplementedError
