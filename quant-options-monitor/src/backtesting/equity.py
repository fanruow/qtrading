"""Simple equity signal backtester."""

from __future__ import annotations

import pandas as pd

from src.backtesting.metrics import cagr, max_drawdown, profit_factor, sharpe, win_rate


def run_equity_signal_backtest(
    prices: pd.DataFrame,
    signals: pd.Series,
    initial_capital: float = 100_000.0,
) -> dict[str, float | pd.Series]:
    returns = prices["close"].pct_change().fillna(0)
    strategy_returns = signals.shift().fillna(0).clip(-1, 1) * returns
    equity_curve = initial_capital * (1 + strategy_returns).cumprod()
    return {
        "equity_curve": equity_curve,
        "CAGR": cagr(equity_curve),
        "Sharpe": sharpe(strategy_returns),
        "max_drawdown": max_drawdown(equity_curve),
        "win_rate": win_rate(strategy_returns),
        "profit_factor": profit_factor(strategy_returns),
    }
