from __future__ import annotations

import numpy as np
import pandas as pd

from src.factors.processing import add_processed_subfactor_columns


LOW_VOL_SUBFACTORS = ["neg_vol_63", "neg_vol_126", "neg_beta_252"]


def _beta(asset: pd.Series, market: pd.Series) -> float:
    df = pd.concat([asset, market], axis=1).dropna()
    if len(df) < 2 or df.iloc[:, 1].var() == 0:
        return np.nan
    return df.iloc[:, 0].cov(df.iloc[:, 1]) / df.iloc[:, 1].var()


def low_vol_raw(as_of: pd.Timestamp, close: pd.DataFrame, tickers: list[str], benchmark: str = "SPY") -> pd.DataFrame:
    loc = close.index.get_loc(pd.Timestamp(as_of))
    ret = close.pct_change(fill_method=None)
    out = pd.DataFrame(index=tickers)
    market = ret[benchmark].iloc[max(0, loc - 251) : loc + 1] if benchmark in ret else pd.Series(dtype=float)
    for ticker in tickers:
        r = ret[ticker]
        out.loc[ticker, "vol_63"] = r.iloc[max(0, loc - 62) : loc + 1].std() * np.sqrt(252)
        out.loc[ticker, "vol_126"] = r.iloc[max(0, loc - 125) : loc + 1].std() * np.sqrt(252)
        out.loc[ticker, "beta_252"] = _beta(r.iloc[max(0, loc - 251) : loc + 1], market)
    out["neg_vol_63"] = -out["vol_63"]
    out["neg_vol_126"] = -out["vol_126"]
    out["neg_beta_252"] = -out["beta_252"]
    return out


def low_vol_score(as_of: pd.Timestamp, close: pd.DataFrame, universe: pd.DataFrame, benchmark="SPY", lower=0.01, upper=0.99, max_missing=2) -> pd.DataFrame:
    raw = low_vol_raw(as_of, close, list(universe.index), benchmark)
    out = add_processed_subfactor_columns(raw, LOW_VOL_SUBFACTORS, universe["sector"], lower, upper)
    z_cols = [f"{c}_sector_z" for c in LOW_VOL_SUBFACTORS]
    out["low_vol_missing_count"] = raw[["vol_63", "vol_126", "beta_252"]].isna().sum(axis=1)
    out["low_vol_score"] = out[z_cols].mean(axis=1, skipna=True).where(out["low_vol_missing_count"] <= max_missing)
    return out
