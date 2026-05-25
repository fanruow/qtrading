from __future__ import annotations

import pandas as pd

from src.factors.processing import sector_neutral_zscore, winsorize_series


def test_sector_zscore_only_within_sector():
    values = pd.Series({"A": 1.0, "B": 3.0, "C": 100.0, "D": 104.0})
    sectors = pd.Series({"A": "Tech", "B": "Tech", "C": "Energy", "D": "Energy"})
    z = sector_neutral_zscore(values, sectors)
    assert z.loc["A"] == -1.0
    assert z.loc["B"] == 1.0
    assert z.loc["C"] == -1.0
    assert z.loc["D"] == 1.0


def test_winsorization_limits_extreme_values():
    s = pd.Series([0.0, 1.0, 2.0, 100.0])
    w = winsorize_series(s, 0.25, 0.75)
    assert w.min() >= s.quantile(0.25)
    assert w.max() <= s.quantile(0.75)
