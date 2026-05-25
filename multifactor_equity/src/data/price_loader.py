from __future__ import annotations

from src.data.providers.base import PriceData, PriceDataProvider as PriceLoader
from src.data.providers.yfinance_price import MockPriceProvider, YFinancePriceProvider


class YFinancePriceLoader(YFinancePriceProvider):
    def load(self, tickers: list[str], start: str, end: str) -> PriceData:
        return self.load_prices(tickers, start, end)


class MockPriceLoader(MockPriceProvider):
    def load(self, tickers: list[str], start: str, end: str) -> PriceData:
        return self.load_prices(tickers, start, end)


def make_price_loader(source: str) -> PriceLoader:
    if source == "yfinance":
        return YFinancePriceLoader()
    if source == "mock":
        return MockPriceLoader()
    raise ValueError(f"unknown price source: {source}")
