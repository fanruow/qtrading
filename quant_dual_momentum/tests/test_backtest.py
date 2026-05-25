import numpy as np
import pandas as pd

from src.backtest import run_dual_momentum_backtest


def test_transaction_cost_is_deducted_on_rebalance_day():
    dates = pd.bdate_range("2020-01-01", periods=90)
    prices = pd.DataFrame({"SPY": np.linspace(100, 200, len(dates))}, index=dates)

    result = run_dual_momentum_backtest(
        prices,
        top_n=1,
        short_lag=2,
        long_lag=20,
        ma_window=5,
        vol_window=3,
        transaction_cost_rate=0.001,
    )
    log = result["rebalance_log"]
    returns = prices.pct_change(fill_method=None).fillna(0.0)
    first_execution = log["execution_date"].iloc[0]
    first_cost = log["cost"].iloc[0]

    expected_return = returns.loc[first_execution, "SPY"] - first_cost
    assert np.isclose(result["returns"].loc[first_execution], expected_return)


def test_strategy_signal_executes_on_next_trading_day_not_signal_day():
    dates = pd.bdate_range("2020-01-01", periods=90)
    prices = pd.DataFrame({"SPY": np.linspace(100, 200, len(dates))}, index=dates)

    result = run_dual_momentum_backtest(
        prices,
        top_n=1,
        short_lag=2,
        long_lag=20,
        ma_window=5,
        vol_window=3,
    )
    log = result["rebalance_log"]
    first_signal = log["signal_date"].iloc[0]
    first_execution = log["execution_date"].iloc[0]

    assert first_execution > first_signal
    assert result["weights"].loc[first_signal].sum() == 0.0
    assert result["weights"].loc[first_execution].sum() > 0.0
