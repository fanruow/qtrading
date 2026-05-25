from __future__ import annotations

import pandas as pd

from src.data.providers.base import FundamentalDataProvider, MetadataProvider


class LocalMetadataProvider(MetadataProvider):
    def __init__(self, fundamentals_provider: FundamentalDataProvider, cache_enabled: bool = True):
        self.fundamentals_provider = fundamentals_provider
        self.cache_enabled = cache_enabled
        self._cache: pd.DataFrame | None = None

    def load_metadata(self) -> pd.DataFrame:
        if self.cache_enabled and self._cache is not None:
            return self._cache.copy()
        cols = [
            "ticker",
            "sector",
            "security_type",
            "is_adr",
            "is_etf",
            "is_otc",
            "is_preferred",
            "available_date",
            "market_cap",
        ]
        fundamentals = self.fundamentals_provider.load_fundamentals()
        metadata = fundamentals[[c for c in cols if c in fundamentals.columns]].copy()
        if self.cache_enabled:
            self._cache = metadata.copy()
        return metadata
