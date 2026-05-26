"""Backtest performance metrics."""

from __future__ import annotations

import numpy as np
import pandas as pd


def cagr(equity_curve: pd.Series, periods_per_year: int = 252) -> float:
    if len(equity_curve) < 2:
        return 0.0
    total_return = equity_curve.iloc[-1] / equity_curve.iloc[0] - 1
    years = len(equity_curve) / periods_per_year
    return float((1 + total_return) ** (1 / years) - 1)


def sharpe(returns: pd.Series, periods_per_year: int = 252) -> float:
    std = returns.std()
    if std == 0 or np.isnan(std):
        return 0.0
    return float(returns.mean() / std * np.sqrt(periods_per_year))


def max_drawdown(equity_curve: pd.Series) -> float:
    running_max = equity_curve.cummax()
    drawdowns = equity_curve / running_max - 1
    return float(drawdowns.min())


def win_rate(returns: pd.Series) -> float:
    nonzero = returns[returns != 0]
    if nonzero.empty:
        return 0.0
    return float((nonzero > 0).mean())


def profit_factor(returns: pd.Series) -> float:
    gains = returns[returns > 0].sum()
    losses = returns[returns < 0].abs().sum()
    if losses == 0:
        return float("inf") if gains > 0 else 0.0
    return float(gains / losses)
