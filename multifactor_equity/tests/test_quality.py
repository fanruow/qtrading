from __future__ import annotations

import pandas as pd

from src.factors.quality import quality_raw


def test_quality_debt_and_accruals_are_inverted():
    u = pd.DataFrame(
        {
            "book_equity": [100.0, 100.0],
            "net_income_ttm": [10.0, 10.0],
            "gross_profit_ttm": [30.0, 30.0],
            "revenue_ttm": [100.0, 100.0],
            "total_debt": [10.0, 80.0],
            "operating_cash_flow_ttm": [12.0, 2.0],
            "total_assets": [200.0, 200.0],
        },
        index=["GOOD", "BAD"],
    )
    raw = quality_raw(u)
    assert raw.loc["GOOD", "neg_debt_to_equity"] > raw.loc["BAD", "neg_debt_to_equity"]
    assert raw.loc["GOOD", "neg_accruals"] > raw.loc["BAD", "neg_accruals"]
