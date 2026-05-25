from __future__ import annotations

import pandas as pd

from src.portfolio.constraints import apply_long_only_constraints


def construct_portfolio(factor_scores: pd.DataFrame, top_n: int, max_stock_weight: float, max_sector_weight: float) -> pd.Series:
    selected = factor_scores.sort_values("composite_score", ascending=False).head(top_n)
    return apply_long_only_constraints(selected, max_stock_weight, max_sector_weight)
