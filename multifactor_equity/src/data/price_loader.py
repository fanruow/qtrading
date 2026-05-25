from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class PriceData:
    close: pd.DataFrame
    volume: pd.DataFrame


class PriceLoader:
    def load(self, tickers: list[str], start: str, end: str) -> PriceData:
        raise NotImplementedError


class YFinancePriceLoader(PriceLoader):
    def load(self, tickers: list[str], start: str, end: str) -> PriceData:
        import yfinance as yf

        raw = yf.download(tickers, start=start, end=end, auto_adjust=True, progress=False, group_by="column")
        if len(tickers) == 1:
            close = raw[["Close"]].rename(columns={"Close": tickers[0]})
            volume = raw[["Volume"]].rename(columns={"Volume": tickers[0]})
        else:
            close = raw["Close"]
            volume = raw["Volume"]
        return PriceData(close=close.sort_index(), volume=volume.sort_index())


class MockPriceLoader(PriceLoader):
    def load(self, tickers: list[str], start: str, end: str) -> PriceData:
        dates = pd.bdate_range(start=start, end=end)
        rng = np.random.default_rng(7)
        close = pd.DataFrame(index=dates, columns=tickers, dtype=float)
        volume = pd.DataFrame(index=dates, columns=tickers, dtype=float)
        for i, ticker in enumerate(tickers):
            drift = 0.00012 + (i % 5) * 0.00003
            vol = 0.012 + (i % 4) * 0.002
            shocks = rng.normal(drift, vol, len(dates))
            close[ticker] = 50 + i * 4
            close[ticker] = close[ticker].iloc[0] * np.exp(np.cumsum(shocks))
            volume[ticker] = rng.integers(1_000_000, 8_000_000, len(dates)) * (8 + (i % 6))
        spy = "SPY"
        if spy not in close.columns:
            shocks = rng.normal(0.00015, 0.011, len(dates))
            close[spy] = 300 * np.exp(np.cumsum(shocks))
            volume[spy] = rng.integers(50_000_000, 90_000_000, len(dates))
        return PriceData(close=close, volume=volume)


def make_price_loader(source: str) -> PriceLoader:
    if source == "yfinance":
        return YFinancePriceLoader()
    if source == "mock":
        return MockPriceLoader()
    raise ValueError(f"unknown price source: {source}")
