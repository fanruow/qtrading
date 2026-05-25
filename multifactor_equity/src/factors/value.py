from __future__ import annotations

import numpy as np
import pandas as pd

from src.factors.processing import add_processed_subfactor_columns


VALUE_SUBFACTORS = ["earnings_yield", "fcf_yield", "book_to_market", "sales_to_price"]


def value_raw(universe: pd.DataFrame) -> pd.DataFrame:
    u = universe.copy()
    out = pd.DataFrame(index=u.index)
    out["earnings_yield"] = u["net_income_ttm"] / u["market_cap"]
    out["fcf_yield"] = u["free_cash_flow_ttm"] / u["enterprise_value"].replace(0, np.nan)
    out["book_to_market"] = u["book_value"] / u["market_cap"]
    out["sales_to_price"] = u["revenue_ttm"] / u["market_cap"]
    return out


def value_score(universe: pd.DataFrame, lower=0.01, upper=0.99, max_missing=2) -> pd.DataFrame:
    raw = value_raw(universe)
    out = add_processed_subfactor_columns(raw, VALUE_SUBFACTORS, universe["sector"], lower, upper)
    z_cols = [f"{c}_sector_z" for c in VALUE_SUBFACTORS]
    out["value_missing_count"] = raw[VALUE_SUBFACTORS].isna().sum(axis=1)
    out["value_score"] = out[z_cols].mean(axis=1, skipna=True).where(out["value_missing_count"] <= max_missing)
    return out
