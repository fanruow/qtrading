from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class BrokerAccount:
    equity: float
    cash: float
    buying_power: float


@dataclass(frozen=True)
class BrokerPosition:
    ticker: str
    market_value: float
    qty: float


@dataclass(frozen=True)
class LiveOrder:
    ticker: str
    side: str
    qty: float
    order_type: str
    time_in_force: str
    client_order_id: str
    decision: str
    reason_summary: str


class BrokerInterface(ABC):
    @abstractmethod
    def assert_paper(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def is_market_open(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def get_account(self) -> BrokerAccount:
        raise NotImplementedError

    @abstractmethod
    def get_positions(self) -> list[BrokerPosition]:
        raise NotImplementedError

    @abstractmethod
    def submit_order(self, order: LiveOrder) -> dict[str, Any]:
        raise NotImplementedError
