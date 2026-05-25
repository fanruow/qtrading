from __future__ import annotations

import pandas as pd
import pytest

from src.data.fundamental_loader import FundamentalLoader
from src.data.providers.base import FundamentalDataProvider, MetadataProvider, PriceDataProvider
from src.data.providers.alpaca_price import AlpacaPriceProvider
from src.data.providers.csv_fundamental import CSVFundamentalProvider, REQUIRED_FUNDAMENTAL_COLUMNS
from src.data.providers.factory import make_fundamental_provider, make_metadata_provider, make_price_provider
from src.data.providers.local_metadata import LocalMetadataProvider
from src.data.providers.yfinance_price import MockPriceProvider, YFinancePriceProvider


def test_provider_factory_uses_configured_interfaces():
    config = {
        "data": {
            "price_provider": "mock",
            "fundamental_provider": "csv",
            "metadata_provider": "local",
            "cache_enabled": True,
            "fundamentals_path": "data/fundamentals_sample.csv",
        }
    }

    price_provider = make_price_provider(config)
    fundamental_provider = make_fundamental_provider(config)
    metadata_provider = make_metadata_provider(config, fundamental_provider)

    assert isinstance(price_provider, PriceDataProvider)
    assert isinstance(price_provider, MockPriceProvider)
    assert isinstance(fundamental_provider, FundamentalDataProvider)
    assert isinstance(fundamental_provider, CSVFundamentalProvider)
    assert isinstance(metadata_provider, MetadataProvider)
    assert isinstance(metadata_provider, LocalMetadataProvider)


def test_csv_fundamental_provider_and_legacy_loader_are_compatible():
    provider = CSVFundamentalProvider("data/fundamentals_sample.csv")
    legacy_loader = FundamentalLoader("data/fundamentals_sample.csv")

    provider_df = provider.load_fundamentals()
    legacy_df = legacy_loader.load()

    assert not provider_df.empty
    assert list(provider_df.columns) == list(legacy_df.columns)
    assert provider_df["available_date"].max() == legacy_df["available_date"].max()


def test_provider_outputs_expected_schema():
    price_provider = MockPriceProvider()
    prices = price_provider.load_prices(["AAA", "BBB"], "2021-01-01", "2021-01-15")
    prices.validate()
    assert set(["AAA", "BBB"]).issubset(prices.close.columns)
    for frame in [prices.open, prices.high, prices.low, prices.close, prices.volume]:
        assert isinstance(frame, pd.DataFrame)
        assert frame.index.equals(prices.close.index)
        assert list(frame.columns) == list(prices.close.columns)

    fundamentals = CSVFundamentalProvider("data/fundamentals_sample.csv").load_fundamentals()
    assert set(REQUIRED_FUNDAMENTAL_COLUMNS).issubset(fundamentals.columns)


def test_csv_fundamental_provider_asof_blocks_future_available_date(tmp_path):
    row_old = {col: 1 for col in REQUIRED_FUNDAMENTAL_COLUMNS}
    row_new = {col: 2 for col in REQUIRED_FUNDAMENTAL_COLUMNS}
    for row, ticker, report_date, available_date, market_cap in [
        (row_old, "AAA", "2020-03-31", "2020-05-01", 1_000_000_000),
        (row_new, "AAA", "2020-06-30", "2020-08-15", 9_000_000_000),
    ]:
        row.update(
            {
                "ticker": ticker,
                "sector": "Tech",
                "security_type": "Common Stock",
                "is_adr": False,
                "is_etf": False,
                "is_otc": False,
                "is_preferred": False,
                "report_date": report_date,
                "available_date": available_date,
                "market_cap": market_cap,
            }
        )
    path = tmp_path / "fundamentals.csv"
    pd.DataFrame([row_old, row_new]).to_csv(path, index=False)

    asof = CSVFundamentalProvider(path).fundamentals_asof(pd.Timestamp("2020-07-31"))

    assert asof.loc["AAA", "market_cap"] == 1_000_000_000


def test_csv_fundamental_provider_missing_fields_error_is_clear(tmp_path):
    path = tmp_path / "bad_fundamentals.csv"
    pd.DataFrame({"ticker": ["AAA"], "available_date": ["2020-01-01"]}).to_csv(path, index=False)

    with pytest.raises(ValueError, match="fundamentals missing required columns"):
        CSVFundamentalProvider(path).load_fundamentals()


def test_yfinance_price_provider_mock_download_returns_ohlcv_schema():
    dates = pd.bdate_range("2021-01-01", periods=3)
    tickers = ["AAA", "BBB"]
    fields = ["Open", "High", "Low", "Close", "Volume"]
    columns = pd.MultiIndex.from_product([fields, tickers])
    raw = pd.DataFrame(1.0, index=dates, columns=columns)
    raw[("Volume", "AAA")] = 100
    raw[("Volume", "BBB")] = 200

    class StubYFinanceProvider(YFinancePriceProvider):
        def _download(self, tickers, start, end):
            return raw

    prices = StubYFinanceProvider().load_prices(tickers, "2021-01-01", "2021-01-10")

    prices.validate()
    assert list(prices.open.columns) == tickers
    assert list(prices.high.columns) == tickers
    assert list(prices.low.columns) == tickers
    assert list(prices.close.columns) == tickers
    assert list(prices.volume.columns) == tickers


def test_alpaca_price_provider_requires_env_keys(monkeypatch):
    monkeypatch.delenv("ALPACA_API_KEY", raising=False)
    monkeypatch.delenv("ALPACA_SECRET_KEY", raising=False)
    monkeypatch.setenv("ALPACA_DATA_FEED", "iex")

    with pytest.raises(ValueError, match="ALPACA_API_KEY and ALPACA_SECRET_KEY"):
        AlpacaPriceProvider()


def test_factory_creates_alpaca_price_provider(monkeypatch):
    monkeypatch.setenv("ALPACA_API_KEY", "key")
    monkeypatch.setenv("ALPACA_SECRET_KEY", "secret")
    monkeypatch.setenv("ALPACA_DATA_FEED", "iex")
    config = {
        "data": {
            "price_provider": "alpaca",
            "cache_enabled": True,
        }
    }

    provider = make_price_provider(config)

    assert isinstance(provider, AlpacaPriceProvider)
    assert provider.data_feed == "iex"


def test_alpaca_price_provider_mock_daily_bars_returns_ohlcv_schema(monkeypatch):
    monkeypatch.setenv("ALPACA_API_KEY", "key")
    monkeypatch.setenv("ALPACA_SECRET_KEY", "secret")
    monkeypatch.setenv("ALPACA_DATA_FEED", "iex")
    payload = {
        "bars": {
            "AAA": [
                {"t": "2021-01-04T05:00:00Z", "o": 10, "h": 11, "l": 9, "c": 10.5, "v": 1000},
                {"t": "2021-01-05T05:00:00Z", "o": 10.5, "h": 12, "l": 10, "c": 11.5, "v": 1200},
            ],
            "BBB": [
                {"t": "2021-01-04T05:00:00Z", "o": 20, "h": 21, "l": 19, "c": 20.5, "v": 2000},
                {"t": "2021-01-05T05:00:00Z", "o": 20.5, "h": 22, "l": 20, "c": 21.5, "v": 2200},
            ],
        }
    }

    class StubAlpacaPriceProvider(AlpacaPriceProvider):
        def _download_bars(self, tickers, start, end):
            return payload

    prices = StubAlpacaPriceProvider().load_prices(["AAA", "BBB"], "2021-01-01", "2021-01-10")

    prices.validate()
    assert list(prices.open.columns) == ["AAA", "BBB"]
    assert prices.close.loc[pd.Timestamp("2021-01-04"), "AAA"] == 10.5
    assert prices.volume.loc[pd.Timestamp("2021-01-05"), "BBB"] == 2200
