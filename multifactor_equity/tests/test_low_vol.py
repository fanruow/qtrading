from __future__ import annotations

import numpy as np
import pandas as pd

from src.factors.low_vol import low_vol_score


def test_low_vol_factor_gives_low_vol_higher_score():
    dates = pd.bdate_range("2020-01-01", periods=300)
    rng = np.random.default_rng(1)
    close = pd.DataFrame(index=dates)
    close["LOW1"] = 100 * np.exp(np.cumsum(rng.normal(0, 0.003, len(dates))))
    close["HIGH1"] = 100 * np.exp(np.cumsum(rng.normal(0, 0.03, len(dates))))
    close["LOW2"] = 100 * np.exp(np.cumsum(rng.normal(0, 0.004, len(dates))))
    close["HIGH2"] = 100 * np.exp(np.cumsum(rng.normal(0, 0.035, len(dates))))
    close["SPY"] = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, len(dates))))
    universe = pd.DataFrame({"sector": ["A", "A", "B", "B"]}, index=["LOW1", "HIGH1", "LOW2", "HIGH2"])
    scores = low_vol_score(dates[-1], close, universe)
    assert scores.loc["LOW1", "low_vol_score"] > scores.loc["HIGH1", "low_vol_score"]
    assert scores.loc["LOW2", "low_vol_score"] > scores.loc["HIGH2", "low_vol_score"]
