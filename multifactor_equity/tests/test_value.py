from __future__ import annotations

import pandas as pd

from src.factors.value import value_raw


def test_value_factor_direction_is_higher_is_better():
    u = pd.DataFrame(
        {
            "market_cap": [100.0, 100.0],
            "enterprise_value": [100.0, 100.0],
            "net_income_ttm": [10.0, 5.0],
            "free_cash_flow_ttm": [8.0, 4.0],
            "book_value": [50.0, 20.0],
            "revenue_ttm": [200.0, 100.0],
        },
        index=["HIGH", "LOW"],
    )
    raw = value_raw(u)
    assert (raw.loc["HIGH"] > raw.loc["LOW"]).all()
