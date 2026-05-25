from __future__ import annotations

import numpy as np
import pandas as pd

from src.data.providers.base import PriceData, PriceDataProvider


class YFinancePriceProvider(PriceDataProvider):
    def __init__(self, cache_enabled: bool = True):
        self.cache_enabled = cache_enabled
        self._cache: dict[tuple[tuple[str, ...], str, str], PriceData] = {}

    def _download(self, tickers: list[str], start: str, end: str) -> pd.DataFrame:
        import yfinance as yf

        return yf.download(tickers, start=start, end=end, auto_adjust=True, progress=False, group_by="column")

    def load_prices(self, tickers: list[str], start: str, end: str) -> PriceData:
        key = (tuple(tickers), start, end)
        if self.cache_enabled and key in self._cache:
            return self._cache[key]
        raw = self._download(tickers, start, end)
        if len(tickers) == 1:
            ticker = tickers[0]
            data = PriceData(
                open=raw[["Open"]].rename(columns={"Open": ticker}),
                high=raw[["High"]].rename(columns={"High": ticker}),
                low=raw[["Low"]].rename(columns={"Low": ticker}),
                close=raw[["Close"]].rename(columns={"Close": ticker}),
                volume=raw[["Volume"]].rename(columns={"Volume": ticker}),
            )
        else:
            data = PriceData(
                open=raw["Open"],
                high=raw["High"],
                low=raw["Low"],
                close=raw["Close"],
                volume=raw["Volume"],
            )
        data = PriceData(
            open=data.open.sort_index(),
            high=data.high.sort_index(),
            low=data.low.sort_index(),
            close=data.close.sort_index(),
            volume=data.volume.sort_index(),
        )
        data.validate()
        if self.cache_enabled:
            self._cache[key] = data
        return data


class MockPriceProvider(PriceDataProvider):
    def __init__(self, cache_enabled: bool = True):
        self.cache_enabled = cache_enabled
        self._cache: dict[tuple[tuple[str, ...], str, str], PriceData] = {}

    def load_prices(self, tickers: list[str], start: str, end: str) -> PriceData:
        key = (tuple(tickers), start, end)
        if self.cache_enabled and key in self._cache:
            return self._cache[key]
        dates = pd.bdate_range(start=start, end=end)
        rng = np.random.default_rng(7)
        close = pd.DataFrame(index=dates, columns=tickers, dtype=float)
        volume = pd.DataFrame(index=dates, columns=tickers, dtype=float)
        for i, ticker in enumerate(tickers):
            drift = 0.00012 + (i % 5) * 0.00003
            vol = 0.012 + (i % 4) * 0.002
            shocks = rng.normal(drift, vol, len(dates))
            close[ticker] = (50 + i * 4) * np.exp(np.cumsum(shocks))
            volume[ticker] = rng.integers(1_000_000, 8_000_000, len(dates)) * (8 + (i % 6))
        if "SPY" not in close.columns:
            shocks = rng.normal(0.00015, 0.011, len(dates))
            close["SPY"] = 300 * np.exp(np.cumsum(shocks))
            volume["SPY"] = rng.integers(50_000_000, 90_000_000, len(dates))
        open_ = close * (1 + rng.normal(0, 0.001, close.shape))
        high = pd.concat([open_, close], axis=0).groupby(level=0).max() * 1.002
        low = pd.concat([open_, close], axis=0).groupby(level=0).min() * 0.998
        data = PriceData(open=open_, high=high, low=low, close=close, volume=volume)
        data.validate()
        if self.cache_enabled:
            self._cache[key] = data
        return data
