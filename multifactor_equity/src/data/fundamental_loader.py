from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.utils.validation import require_columns


REQUIRED_COLUMNS = [
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


class FundamentalLoader:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def load(self) -> pd.DataFrame:
        if self.path.suffix.lower() == ".parquet":
            df = pd.read_parquet(self.path)
        else:
            df = pd.read_csv(self.path)
        require_columns(df, REQUIRED_COLUMNS, "fundamentals")
        for c in ["report_date", "available_date"]:
            df[c] = pd.to_datetime(df[c])
        bool_cols = ["is_adr", "is_etf", "is_otc", "is_preferred"]
        for c in bool_cols:
            if df[c].dtype == object:
                df[c] = df[c].astype(str).str.lower().isin(["true", "1", "yes"])
        return df.sort_values(["ticker", "available_date", "report_date"])


def fundamentals_asof(fundamentals: pd.DataFrame, as_of: pd.Timestamp) -> pd.DataFrame:
    eligible = fundamentals[fundamentals["available_date"] <= pd.Timestamp(as_of)].copy()
    eligible = eligible.sort_values(["ticker", "available_date", "report_date"])
    return eligible.groupby("ticker", as_index=False).tail(1).set_index("ticker", drop=False)
