import numpy as np
import pandas as pd

from src.portfolio import (
    apply_volatility_scale,
    calculate_realized_volatility,
    calculate_transaction_cost,
    calculate_turnover,
    calculate_volatility_scale,
)


def test_weight_sum_is_less_than_or_equal_to_one_after_scaling():
    raw = pd.Series({"SPY": 1 / 3, "QQQ": 1 / 3, "IWM": 1 / 3})

    scaled = apply_volatility_scale(raw, 0.5)

    assert scaled.sum() <= 1.0
    assert np.isclose(scaled.sum(), 0.5)


def test_turnover_calculation_is_correct():
    old = pd.Series({"SPY": 0.4, "QQQ": 0.2})
    new = pd.Series({"SPY": 0.1, "QQQ": 0.2, "IEF": 0.3})

    turnover = calculate_turnover(new, old)

    assert np.isclose(turnover, 0.6)


def test_transaction_cost_calculation_is_correct():
    assert calculate_transaction_cost(0.75, 0.001) == 0.00075


def test_volatility_scale_never_exceeds_one():
    realized_vol = pd.Series([0.05, 0.10, 0.20])

    scale = calculate_volatility_scale(realized_vol, target_volatility=0.10)

    assert (scale <= 1.0).all()
    assert np.isclose(scale.iloc[-1], 0.5)


def test_scale_uses_only_trailing_returns_not_future_returns():
    returns = pd.Series([0.01, -0.01, 0.02, -0.02, 0.50], index=pd.bdate_range("2024-01-01", periods=5))

    vol_before_future = calculate_realized_volatility(returns.iloc[:4], window=3).iloc[-1]
    vol_with_future_shifted = calculate_realized_volatility(returns, window=3).shift(1).iloc[4]

    assert np.isclose(vol_before_future, vol_with_future_shifted)
