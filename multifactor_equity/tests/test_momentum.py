from __future__ import annotations

import numpy as np
import pandas as pd

from src.factors.momentum import momentum_raw


def test_12_1_momentum_skips_recent_21_trading_days():
    dates = pd.bdate_range("2020-01-01", periods=300)
    close = pd.DataFrame({"AAA": np.arange(1, 301, dtype=float)}, index=dates)
    as_of = dates[260]
    raw = momentum_raw(as_of, close, ["AAA"])
    loc = close.index.get_loc(as_of)
    expected = close["AAA"].iloc[loc - 21] / close["AAA"].iloc[loc - 252] - 1
    assert raw.loc["AAA", "mom_12_1"] == expected
    assert raw.loc["AAA", "mom_12_1"] != close["AAA"].iloc[loc] / close["AAA"].iloc[loc - 252] - 1
