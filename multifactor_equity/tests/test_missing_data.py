from __future__ import annotations

import pandas as pd

from src.factors.value import value_score


def test_missing_subfactor_handling_is_stable():
    u = pd.DataFrame(
        {
            "sector": ["A", "A", "A"],
            "market_cap": [100.0, 100.0, 100.0],
            "enterprise_value": [100.0, 100.0, 100.0],
            "net_income_ttm": [10.0, None, 5.0],
            "free_cash_flow_ttm": [8.0, None, 4.0],
            "book_value": [50.0, None, 20.0],
            "revenue_ttm": [200.0, 100.0, 100.0],
        },
        index=["A", "B", "C"],
    )
    scores = value_score(u, max_missing=2)
    assert pd.isna(scores.loc["B", "value_score"])
    assert not pd.isna(scores.loc["A", "value_score"])
