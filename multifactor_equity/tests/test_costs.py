from __future__ import annotations

import pandas as pd

from src.backtest.costs import calculate_turnover, trading_cost


def test_turnover_calculation():
    old = pd.Series({"A": 0.2, "B": 0.3})
    new = pd.Series({"A": 0.1, "C": 0.4})
    assert calculate_turnover(new, old) == 0.8


def test_trading_costs():
    costs = trading_cost(0.5, 0.001, 0.001)
    assert costs["commission_cost"] == 0.0005
    assert costs["slippage_cost"] == 0.0005
    assert costs["total_cost"] == 0.001
