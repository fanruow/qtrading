from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.data.providers.base import FundamentalDataProvider
from src.utils.validation import require_columns


REQUIRED_FUNDAMENTAL_COLUMNS = [
    "ticker",
    "sector",
    "security_type",
    "is_adr",
    "is_etf",
    "is_otc",
    "is_preferred",
    "report_date",
    "available_date",
    "market_cap",
    "enterprise_value",
    "net_income_ttm",
    "free_cash_flow_ttm",
    "book_value",
    "book_equity",
    "revenue_ttm",
    "gross_profit_ttm",
    "total_debt",
    "operating_cash_flow_ttm",
    "total_assets",
]


class CSVFundamentalProvider(FundamentalDataProvider):
    def __init__(self, path: str | Path, cache_enabled: bool = True):
        self.path = Path(path)
        self.cache_enabled = cache_enabled
        self._cache: pd.DataFrame | None = None

    def load_fundamentals(self) -> pd.DataFrame:
        if self.cache_enabled and self._cache is not None:
            return self._cache.copy()
        if self.path.suffix.lower() == ".parquet":
            df = pd.read_parquet(self.path)
        else:
            df = pd.read_csv(self.path)
        require_columns(df, REQUIRED_FUNDAMENTAL_COLUMNS, "fundamentals")
        for col in ["report_date", "available_date"]:
            df[col] = pd.to_datetime(df[col])
        for col in ["is_adr", "is_etf", "is_otc", "is_preferred"]:
            if df[col].dtype == object:
                df[col] = df[col].astype(str).str.lower().isin(["true", "1", "yes"])
        df = df.sort_values(["ticker", "available_date", "report_date"]).reset_index(drop=True)
        if self.cache_enabled:
            self._cache = df.copy()
        return df
