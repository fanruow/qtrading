from __future__ import annotations

import pandas as pd

from src.portfolio.constraints import apply_long_only_constraints


def test_portfolio_constraints_weight_sum_stock_and_sector_caps():
    selected = pd.DataFrame(
        {"sector": ["Tech"] * 20 + ["Energy"] * 20 + ["Health"] * 20},
        index=[f"T{i}" for i in range(60)],
    )
    w = apply_long_only_constraints(selected, max_stock_weight=0.025, max_sector_weight=0.25)
    assert w.sum() <= 1.0 + 1e-12
    assert w.max() <= 0.025 + 1e-12
    sector_weights = w.groupby(selected["sector"]).sum()
    assert sector_weights.max() <= 0.25 + 1e-12
