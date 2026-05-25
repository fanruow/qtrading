from __future__ import annotations

import pandas as pd

from src.data.providers.csv_fundamental import CSVFundamentalProvider, REQUIRED_FUNDAMENTAL_COLUMNS


REQUIRED_COLUMNS = REQUIRED_FUNDAMENTAL_COLUMNS


class FundamentalLoader(CSVFundamentalProvider):
    def load(self) -> pd.DataFrame:
        return self.load_fundamentals()


def fundamentals_asof(fundamentals: pd.DataFrame, as_of: pd.Timestamp) -> pd.DataFrame:
    eligible = fundamentals[fundamentals["available_date"] <= pd.Timestamp(as_of)].copy()
    eligible = eligible.sort_values(["ticker", "available_date", "report_date"])
    return eligible.groupby("ticker", as_index=False).tail(1).set_index("ticker", drop=False)
