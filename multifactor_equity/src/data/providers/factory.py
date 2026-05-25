from __future__ import annotations

from src.data.providers.base import FundamentalDataProvider, MetadataProvider, PriceDataProvider
from src.data.providers.csv_fundamental import CSVFundamentalProvider
from src.data.providers.local_metadata import LocalMetadataProvider
from src.data.providers.yfinance_price import MockPriceProvider, YFinancePriceProvider
from src.utils.config import project_path


def make_price_provider(config: dict) -> PriceDataProvider:
    data_cfg = config["data"]
    provider = data_cfg.get("price_provider", "mock")
    cache_enabled = bool(data_cfg.get("cache_enabled", True))
    if provider == "yfinance":
        return YFinancePriceProvider(cache_enabled=cache_enabled)
    if provider == "mock":
        return MockPriceProvider(cache_enabled=cache_enabled)
    raise ValueError(f"unknown price provider: {provider}")


def make_fundamental_provider(config: dict) -> FundamentalDataProvider:
    data_cfg = config["data"]
    provider = data_cfg.get("fundamental_provider", "csv")
    cache_enabled = bool(data_cfg.get("cache_enabled", True))
    if provider == "csv":
        return CSVFundamentalProvider(project_path(data_cfg["fundamentals_path"]), cache_enabled=cache_enabled)
    raise ValueError(f"unknown fundamental provider: {provider}")


def make_metadata_provider(config: dict, fundamental_provider: FundamentalDataProvider) -> MetadataProvider:
    data_cfg = config["data"]
    provider = data_cfg.get("metadata_provider", "local")
    cache_enabled = bool(data_cfg.get("cache_enabled", True))
    if provider == "local":
        return LocalMetadataProvider(fundamental_provider, cache_enabled=cache_enabled)
    raise ValueError(f"unknown metadata provider: {provider}")
