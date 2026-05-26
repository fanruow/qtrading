"""yfinance market data provider."""

from __future__ import annotations

from typing import Any

import pandas as pd

from quant_options_monitor.data.base import BaseMarketDataProvider, MarketDataError


_REQUIRED_COLUMNS = {
    "Open": "open",
    "High": "high",
    "Low": "low",
    "Close": "close",
    "Volume": "volume",
}
_OPTIONAL_COLUMNS = {
    "Adj Close": "adjusted_close",
}


class YFinanceMarketDataProvider(BaseMarketDataProvider):
    """Market data provider backed by yfinance Ticker.history."""

    def __init__(self, yf_module: Any | None = None) -> None:
        if yf_module is None:
            import yfinance as yf_module

        self._yf = yf_module

    def get_price_history(self, symbol: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
        """Fetch and normalize OHLCV history from yfinance."""

        try:
            raw = self._yf.Ticker(symbol).history(
                period=period,
                interval=interval,
                auto_adjust=False,
            )
        except Exception as exc:  # pragma: no cover - exercised via behavior, not exception types
            raise MarketDataError(f"Failed to fetch price history for {symbol}: {exc}") from exc

        return self._normalize_history(symbol, raw)

    def get_latest_price(self, symbol: str) -> float:
        """Return the most recent normalized close price."""

        history = self.get_price_history(symbol=symbol, period="5d", interval="1d")
        close = history["close"].dropna()
        if close.empty:
            raise MarketDataError(f"No latest close price available for {symbol}")
        return float(close.iloc[-1])

    def _normalize_history(self, symbol: str, data: pd.DataFrame) -> pd.DataFrame:
        if data.empty:
            raise MarketDataError(f"No price history returned for {symbol}")

        missing = [column for column in _REQUIRED_COLUMNS if column not in data.columns]
        if missing:
            raise MarketDataError(
                f"Price history for {symbol} is missing required columns: {', '.join(missing)}"
            )

        rename_map = {**_REQUIRED_COLUMNS, **_OPTIONAL_COLUMNS}
        available_columns = [column for column in rename_map if column in data.columns]
        normalized = data.loc[:, available_columns].rename(columns=rename_map)
        ordered_columns = ["open", "high", "low", "close", "volume"]
        if "adjusted_close" in normalized.columns:
            ordered_columns.append("adjusted_close")

        normalized = normalized.loc[:, ordered_columns].copy()
        if normalized[["open", "high", "low", "close", "volume"]].isna().all(axis=None):
            raise MarketDataError(f"Price history for {symbol} contains no usable OHLCV values")
        return normalized
