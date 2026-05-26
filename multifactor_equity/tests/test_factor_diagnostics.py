from __future__ import annotations

import pandas as pd

from src.factors.diagnostics import compute_factor_diagnostics


def test_ic_uses_next_month_forward_return_not_current_month():
    dates = pd.to_datetime(["2020-01-31", "2020-02-28", "2020-03-31"])
    close = pd.DataFrame(
        {
            "A": [100.0, 110.0, 110.0],
            "B": [100.0, 100.0, 130.0],
            "C": [100.0, 90.0, 80.0],
        },
        index=dates,
    )
    fs = pd.DataFrame(
        {
            "signal_date": [dates[0]] * 3 + [dates[1]] * 3,
            "ticker": ["A", "B", "C"] * 2,
            "momentum_score": [1.0, 2.0, 3.0, 1.0, 2.0, 3.0],
            "quality_score": [1.0, 2.0, 3.0, 1.0, 2.0, 3.0],
            "value_score": [1.0, 2.0, 3.0, 1.0, 2.0, 3.0],
            "low_vol_score": [1.0, 2.0, 3.0, 1.0, 2.0, 3.0],
            "composite_score": [1.0, 2.0, 3.0, 1.0, 2.0, 3.0],
        }
    )
    ic, _ = compute_factor_diagnostics(fs, close)
    first = ic[(ic["signal_date"] == dates[0]) & (ic["factor"] == "composite_score")]["ic"].iloc[0]
    assert first < 0  # Jan signal compares against Feb returns: A up, C down.


def test_ic_handles_sparse_cross_sections_without_pd_na_std_error():
    dates = pd.to_datetime(["2020-01-31", "2020-02-28"])
    close = pd.DataFrame({"A": [100.0, 101.0], "B": [100.0, 99.0]}, index=dates)
    fs = pd.DataFrame(
        {
            "signal_date": [dates[0], dates[0], dates[1], dates[1]],
            "ticker": ["A", "B", "A", "B"],
            "momentum_score": [1.0, 2.0, 1.0, 2.0],
            "quality_score": [1.0, 2.0, 1.0, 2.0],
            "value_score": [1.0, 2.0, 1.0, 2.0],
            "low_vol_score": [1.0, 2.0, 1.0, 2.0],
            "composite_score": [1.0, 2.0, 1.0, 2.0],
        }
    )

    ic, _ = compute_factor_diagnostics(fs, close)

    assert ic["ic"].isna().all()
    assert "ic_std" in ic.columns
