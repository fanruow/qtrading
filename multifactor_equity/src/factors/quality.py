from __future__ import annotations

import numpy as np
import pandas as pd

from src.factors.processing import add_processed_subfactor_columns


QUALITY_SUBFACTORS = ["roe", "gross_margin", "neg_debt_to_equity", "neg_accruals"]


def quality_raw(universe: pd.DataFrame) -> pd.DataFrame:
    u = universe.copy()
    out = pd.DataFrame(index=u.index)
    book_equity = u["book_equity"].replace(0, np.nan)
    revenue = u["revenue_ttm"].replace(0, np.nan)
    assets = u["total_assets"].replace(0, np.nan)
    out["roe"] = u["net_income_ttm"] / book_equity
    out["gross_margin"] = u["gross_profit_ttm"] / revenue
    out["debt_to_equity"] = u["total_debt"] / book_equity
    out["accruals"] = (u["net_income_ttm"] - u["operating_cash_flow_ttm"]) / assets
    out["neg_debt_to_equity"] = -out["debt_to_equity"]
    out["neg_accruals"] = -out["accruals"]
    return out


def quality_score(universe: pd.DataFrame, lower=0.01, upper=0.99, max_missing=2) -> pd.DataFrame:
    raw = quality_raw(universe)
    out = add_processed_subfactor_columns(raw, QUALITY_SUBFACTORS, universe["sector"], lower, upper)
    z_cols = [f"{c}_sector_z" for c in QUALITY_SUBFACTORS]
    out["quality_missing_count"] = raw[["roe", "gross_margin", "debt_to_equity", "accruals"]].isna().sum(axis=1)
    out["quality_score"] = out[z_cols].mean(axis=1, skipna=True).where(out["quality_missing_count"] <= max_missing)
    return out
