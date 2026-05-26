"""Base market data provider contracts."""

from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class MarketDataError(RuntimeError):
    """Raised when market data cannot be fetched or normalized safely."""


class BaseMarketDataProvider(ABC):
    """Typed interface for equity market data providers."""

    @abstractmethod
    def get_price_history(self, symbol: str, period: str, interval: str) -> pd.DataFrame:
        """Return normalized OHLCV price history for one symbol."""

    @abstractmethod
    def get_latest_price(self, symbol: str) -> float:
        """Return the latest available close price for one symbol."""

    def get_watchlist_history(
        self, symbols: list[str], period: str, interval: str
    ) -> dict[str, pd.DataFrame]:
        """Return normalized OHLCV history keyed by symbol."""

        return {
            symbol: self.get_price_history(symbol=symbol, period=period, interval=interval)
            for symbol in symbols
        }
