from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import pytest

from quant_options_monitor.data import BaseMarketDataProvider, MarketDataError, YFinanceMarketDataProvider


class DummyProvider(BaseMarketDataProvider):
    def __init__(self, frames: dict[str, pd.DataFrame]) -> None:
        self.frames = frames

    def get_price_history(self, symbol: str, period: str, interval: str) -> pd.DataFrame:
        return self.frames[symbol]

    def get_latest_price(self, symbol: str) -> float:
        return float(self.frames[symbol]["close"].iloc[-1])


@dataclass
class FakeTicker:
    frame: pd.DataFrame

    def history(self, period: str, interval: str, auto_adjust: bool) -> pd.DataFrame:
        assert period
        assert interval
        assert auto_adjust is False
        return self.frame


class FakeYFinance:
    def __init__(self, frames: dict[str, pd.DataFrame]) -> None:
        self.frames = frames

    def Ticker(self, symbol: str) -> FakeTicker:
        return FakeTicker(self.frames[symbol])


def yfinance_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Open": [100.0, 101.0],
            "High": [102.0, 103.0],
            "Low": [99.0, 100.0],
            "Close": [101.0, 102.0],
            "Volume": [1_000_000, 1_100_000],
            "Adj Close": [100.5, 101.5],
        },
        index=pd.date_range("2024-01-01", periods=2),
    )


def test_yfinance_provider_normalizes_ohlcv_columns() -> None:
    provider = YFinanceMarketDataProvider(yf_module=FakeYFinance({"SPY": yfinance_frame()}))

    history = provider.get_price_history("SPY", period="1mo", interval="1d")

    assert list(history.columns) == ["open", "high", "low", "close", "volume", "adjusted_close"]
    assert history["close"].iloc[-1] == 102.0


def test_yfinance_provider_latest_price_uses_last_close() -> None:
    provider = YFinanceMarketDataProvider(yf_module=FakeYFinance({"SPY": yfinance_frame()}))

    assert provider.get_latest_price("SPY") == 102.0


def test_yfinance_provider_empty_data_raises_market_data_error() -> None:
    provider = YFinanceMarketDataProvider(yf_module=FakeYFinance({"SPY": pd.DataFrame()}))

    with pytest.raises(MarketDataError, match="No price history"):
        provider.get_price_history("SPY", period="1mo", interval="1d")


def test_yfinance_provider_missing_required_columns_raises_market_data_error() -> None:
    frame = yfinance_frame().drop(columns=["Volume"])
    provider = YFinanceMarketDataProvider(yf_module=FakeYFinance({"SPY": frame}))

    with pytest.raises(MarketDataError, match="missing required columns: Volume"):
        provider.get_price_history("SPY", period="1mo", interval="1d")


def test_base_provider_watchlist_history_aggregates_symbols() -> None:
    provider = DummyProvider(
        {
            "SPY": pd.DataFrame({"close": [100.0]}),
            "QQQ": pd.DataFrame({"close": [200.0]}),
        }
    )

    history = provider.get_watchlist_history(["SPY", "QQQ"], period="1mo", interval="1d")

    assert set(history) == {"SPY", "QQQ"}
    assert history["QQQ"]["close"].iloc[-1] == 200.0
