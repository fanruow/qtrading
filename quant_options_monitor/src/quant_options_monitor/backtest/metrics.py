"""Backtest performance metrics."""

from __future__ import annotations

import numpy as np
import pandas as pd


def total_return(equity_curve: pd.Series) -> float:
    if len(equity_curve) < 2 or equity_curve.iloc[0] == 0:
        return 0.0
    return float(equity_curve.iloc[-1] / equity_curve.iloc[0] - 1)


def cagr(equity_curve: pd.Series, periods_per_year: int = 252) -> float:
    if len(equity_curve) < 2 or equity_curve.iloc[0] <= 0:
        return 0.0
    years = len(equity_curve) / periods_per_year
    if years <= 0:
        return 0.0
    return float((equity_curve.iloc[-1] / equity_curve.iloc[0]) ** (1 / years) - 1)


def annualized_volatility(returns: pd.Series, periods_per_year: int = 252) -> float:
    std = returns.std(ddof=0)
    if pd.isna(std):
        return 0.0
    return float(std * np.sqrt(periods_per_year))


def sharpe(returns: pd.Series, periods_per_year: int = 252) -> float:
    vol = annualized_volatility(returns, periods_per_year=periods_per_year)
    if vol == 0:
        return 0.0
    return float(returns.mean() * periods_per_year / vol)


def max_drawdown(equity_curve: pd.Series) -> float:
    if equity_curve.empty:
        return 0.0
    drawdown = equity_curve / equity_curve.cummax() - 1
    return float(drawdown.min())


def win_rate(returns: pd.Series) -> float:
    active = returns[returns != 0]
    if active.empty:
        return 0.0
    return float((active > 0).mean())


def profit_factor(returns: pd.Series) -> float:
    gross_profit = returns[returns > 0].sum()
    gross_loss = returns[returns < 0].abs().sum()
    if gross_loss == 0:
        return float("inf") if gross_profit > 0 else 0.0
    return float(gross_profit / gross_loss)


def number_of_trades(positions: pd.Series) -> int:
    if positions.empty:
        return 0
    return int(positions.diff().abs().fillna(positions.abs()).gt(0).sum())


def calculate_metrics(
    equity_curve: pd.Series,
    strategy_returns: pd.Series,
    positions: pd.Series,
    periods_per_year: int = 252,
) -> dict[str, float | int]:
    """Calculate standard performance metrics."""

    return {
        "total_return": total_return(equity_curve),
        "cagr": cagr(equity_curve, periods_per_year=periods_per_year),
        "annualized_volatility": annualized_volatility(
            strategy_returns, periods_per_year=periods_per_year
        ),
        "sharpe": sharpe(strategy_returns, periods_per_year=periods_per_year),
        "max_drawdown": max_drawdown(equity_curve),
        "win_rate": win_rate(strategy_returns),
        "profit_factor": profit_factor(strategy_returns),
        "number_of_trades": number_of_trades(positions),
    }
