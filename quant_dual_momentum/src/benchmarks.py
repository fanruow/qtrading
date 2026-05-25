"""Benchmark portfolio calculations."""

from __future__ import annotations

import pandas as pd

from .data import compute_daily_returns
from .signals import get_month_end_trading_days, map_signal_dates_to_execution_dates


def buy_and_hold_returns(returns: pd.DataFrame, ticker: str) -> pd.Series:
    """Return buy-and-hold daily returns for one ticker."""
    series = returns[ticker].fillna(0.0).copy()
    series.name = f"{ticker} Buy & Hold"
    return series


def monthly_rebalanced_static_portfolio(
    returns: pd.DataFrame,
    target_weights: dict[str, float],
    name: str,
) -> pd.Series:
    """Backtest a static target-weight portfolio rebalanced monthly."""
    signal_dates = get_month_end_trading_days(returns.index)
    execution_dates = pd.DatetimeIndex(map_signal_dates_to_execution_dates(signal_dates, returns.index).values)
    target = pd.Series(target_weights).reindex(returns.columns).fillna(0.0)
    current = pd.Series(0.0, index=returns.columns)
    out = pd.Series(0.0, index=returns.index, name=name)
    execution_set = set(execution_dates)

    for date in returns.index:
        if date in execution_set:
            current = target.copy()
        out.loc[date] = float((current * returns.loc[date].fillna(0.0)).sum())
    return out


def build_benchmark_returns(prices: pd.DataFrame, universe: list[str]) -> pd.DataFrame:
    """Build benchmark daily returns for SPY, 60/40, and monthly equal weight."""
    returns = compute_daily_returns(prices).fillna(0.0)
    ew_weight = 1.0 / len(universe)
    benchmark_returns = pd.concat(
        [
            buy_and_hold_returns(returns, "SPY"),
            monthly_rebalanced_static_portfolio(returns, {"SPY": 0.6, "IEF": 0.4}, "60/40 SPY/IEF"),
            monthly_rebalanced_static_portfolio(
                returns,
                {ticker: ew_weight for ticker in universe},
                "ETF Equal Weight",
            ),
        ],
        axis=1,
    )
    return benchmark_returns
