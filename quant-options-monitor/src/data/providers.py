"""Market data provider abstractions and yfinance fallback implementation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date, datetime, timezone

import pandas as pd

from src.data.models import OptionContract


def _clean_float(value: object, default: float = 0.0) -> float:
    if value is None or pd.isna(value):
        return default
    return float(value)


def _clean_int(value: object, default: int = 0) -> int:
    if value is None or pd.isna(value):
        return default
    return int(value)


class BaseMarketDataProvider(ABC):
    """Abstract market data provider used by research, strategy, and alerts."""

    @abstractmethod
    def get_price_history(self, symbol: str, period: str = "1y") -> pd.DataFrame:
        """Return OHLCV history indexed by timestamp."""

    @abstractmethod
    def get_option_chain(self, symbol: str, expiration: date | None = None) -> list[OptionContract]:
        """Return normalized option contracts for a symbol."""

    @abstractmethod
    def get_expirations(self, symbol: str) -> list[date]:
        """Return listed option expiration dates."""


class YFinanceMarketDataProvider(BaseMarketDataProvider):
    """yfinance-backed provider for research and fallback data access."""

    def __init__(self) -> None:
        import yfinance as yf

        self._yf = yf

    def get_price_history(self, symbol: str, period: str = "1y") -> pd.DataFrame:
        ticker = self._yf.Ticker(symbol)
        data = ticker.history(period=period, auto_adjust=False)
        if data.empty:
            raise ValueError(f"No price history returned for {symbol}")
        data = data.rename(columns=str.lower)
        return data[["open", "high", "low", "close", "volume"]].dropna()

    def get_expirations(self, symbol: str) -> list[date]:
        expirations = self._yf.Ticker(symbol).options
        return [datetime.strptime(exp, "%Y-%m-%d").date() for exp in expirations]

    def get_option_chain(self, symbol: str, expiration: date | None = None) -> list[OptionContract]:
        ticker = self._yf.Ticker(symbol)
        exp = expiration or self.get_expirations(symbol)[0]
        raw = ticker.option_chain(exp.isoformat())
        contracts: list[OptionContract] = []
        for right, frame in (("call", raw.calls), ("put", raw.puts)):
            for row in frame.to_dict("records"):
                contracts.append(
                    OptionContract(
                        symbol=symbol,
                        expiration=exp,
                        strike=_clean_float(row["strike"]),
                        right=right,
                        bid=_clean_float(row.get("bid", 0.0)),
                        ask=_clean_float(row.get("ask", 0.0)),
                        last=_clean_float(row.get("lastPrice", 0.0)),
                        volume=_clean_int(row.get("volume", 0)),
                        open_interest=_clean_int(row.get("openInterest", 0)),
                        implied_volatility=_clean_float(row.get("impliedVolatility", 0.0)),
                    )
                )
        return contracts


class SyntheticMarketDataProvider(BaseMarketDataProvider):
    """Deterministic provider used by tests and demos when live data is unavailable."""

    def get_price_history(self, symbol: str, period: str = "1y") -> pd.DataFrame:
        idx = pd.date_range(end=datetime.now(timezone.utc).date(), periods=260, freq="B")
        base = pd.Series(range(len(idx)), index=idx, dtype=float)
        close = 100 + base * 0.1 + (base % 17) * 0.05
        return pd.DataFrame(
            {
                "open": close * 0.998,
                "high": close * 1.01,
                "low": close * 0.99,
                "close": close,
                "volume": 1_000_000 + (base % 21) * 10_000,
            },
            index=idx,
        )

    def get_expirations(self, symbol: str) -> list[date]:
        today = datetime.now(timezone.utc).date()
        return [today + pd.Timedelta(days=days) for days in (30, 45, 60, 90)]

    def get_option_chain(self, symbol: str, expiration: date | None = None) -> list[OptionContract]:
        exp = expiration or self.get_expirations(symbol)[0]
        today = datetime.now(timezone.utc).date()
        dte = max((exp - today).days, 1)
        contracts: list[OptionContract] = []
        for strike in range(80, 125, 5):
            for right in ("call", "put"):
                intrinsic = max(100 - strike, 0) if right == "put" else max(strike - 100, 0)
                premium = max(1.0, 6.0 - abs(strike - 100) * 0.25 + dte / 60)
                delta = 0.5 - (strike - 100) / 100
                contracts.append(
                    OptionContract(
                        symbol=symbol,
                        expiration=exp,
                        strike=float(strike),
                        right=right,  # type: ignore[arg-type]
                        bid=max(premium + intrinsic - 0.05, 0.01),
                        ask=premium + intrinsic + 0.05,
                        last=premium + intrinsic,
                        volume=500,
                        open_interest=2_000,
                        implied_volatility=0.25 + abs(strike - 100) / 400,
                        delta=delta if right == "call" else delta - 1,
                    )
                )
        return contracts
