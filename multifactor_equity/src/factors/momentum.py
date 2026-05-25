from __future__ import annotations

import pandas as pd

from src.factors.processing import add_processed_subfactor_columns


def momentum_raw(as_of: pd.Timestamp, close: pd.DataFrame, tickers: list[str]) -> pd.DataFrame:
    loc = close.index.get_loc(pd.Timestamp(as_of))
    out = pd.DataFrame(index=tickers, columns=["mom_12_1", "mom_6_1"], dtype=float)
    if loc < 252:
        return out
    for ticker in tickers:
        s = close[ticker]
        out.loc[ticker, "mom_12_1"] = s.iloc[loc - 21] / s.iloc[loc - 252] - 1
        out.loc[ticker, "mom_6_1"] = s.iloc[loc - 21] / s.iloc[loc - 126] - 1 if loc >= 126 else pd.NA
    return out


def momentum_score(as_of: pd.Timestamp, close: pd.DataFrame, universe: pd.DataFrame, lower=0.01, upper=0.99) -> pd.DataFrame:
    raw = momentum_raw(as_of, close, list(universe.index))
    result = add_processed_subfactor_columns(raw, ["mom_12_1", "mom_6_1"], universe["sector"], lower, upper)
    result["momentum_score"] = 0.7 * result["mom_12_1_sector_z"] + 0.3 * result["mom_6_1_sector_z"]
    result["momentum_missing_count"] = raw[["mom_12_1", "mom_6_1"]].isna().sum(axis=1)
    return result
