"""Performance metric calculations."""

from __future__ import annotations

import numpy as np
import pandas as pd


def total_return(equity: pd.Series) -> float:
    """Calculate total return from an equity curve."""
    clean = equity.dropna()
    if clean.empty:
        return np.nan
    return float(clean.iloc[-1] / clean.iloc[0] - 1.0)


def cagr(equity: pd.Series, periods_per_year: int = 252) -> float:
    """Calculate CAGR from a daily equity curve."""
    clean = equity.dropna()
    if len(clean) < 2:
        return np.nan
    years = (len(clean) - 1) / periods_per_year
    if years <= 0 or clean.iloc[0] <= 0:
        return np.nan
    return float((clean.iloc[-1] / clean.iloc[0]) ** (1.0 / years) - 1.0)


def annualized_volatility(returns: pd.Series, periods_per_year: int = 252) -> float:
    """Calculate annualized volatility of periodic returns."""
    return float(returns.dropna().std() * np.sqrt(periods_per_year))


def sharpe_ratio(returns: pd.Series, risk_free_rate: float = 0.0, periods_per_year: int = 252) -> float:
    """Calculate annualized Sharpe ratio with a constant annual risk-free rate."""
    excess = returns.dropna() - risk_free_rate / periods_per_year
    vol = excess.std()
    if vol == 0 or pd.isna(vol):
        return np.nan
    return float(excess.mean() / vol * np.sqrt(periods_per_year))


def sortino_ratio(returns: pd.Series, risk_free_rate: float = 0.0, periods_per_year: int = 252) -> float:
    """Calculate annualized Sortino ratio."""
    excess = returns.dropna() - risk_free_rate / periods_per_year
    downside = excess[excess < 0]
    downside_vol = downside.std()
    if downside_vol == 0 or pd.isna(downside_vol):
        return np.nan
    return float(excess.mean() / downside_vol * np.sqrt(periods_per_year))


def drawdown(equity: pd.Series) -> pd.Series:
    """Calculate drawdown curve from an equity curve."""
    clean = equity.dropna()
    return clean / clean.cummax() - 1.0


def max_drawdown(equity: pd.Series) -> float:
    """Calculate maximum drawdown from an equity curve."""
    dd = drawdown(equity)
    if dd.empty:
        return np.nan
    return float(dd.min())


def monthly_returns_from_daily_returns(returns: pd.Series) -> pd.Series:
    """Compound daily returns into calendar monthly returns."""
    return (1.0 + returns.dropna()).resample("ME").prod() - 1.0


def performance_summary(
    returns: pd.DataFrame,
    rebalance_log: pd.DataFrame | None = None,
    periods_per_year: int = 252,
) -> pd.DataFrame:
    """Calculate performance metrics for each return column."""
    equity = (1.0 + returns).cumprod()
    rows: list[dict[str, float | str]] = []
    for column in returns.columns:
        series = returns[column].dropna()
        eq = equity[column].dropna()
        monthly = monthly_returns_from_daily_returns(series)
        row = {
            "name": column,
            "total_return": total_return(eq),
            "cagr": cagr(eq, periods_per_year),
            "annualized_volatility": annualized_volatility(series, periods_per_year),
            "sharpe_ratio": sharpe_ratio(series, periods_per_year=periods_per_year),
            "sortino_ratio": sortino_ratio(series, periods_per_year=periods_per_year),
            "max_drawdown": max_drawdown(eq),
            "calmar_ratio": np.nan,
            "monthly_win_rate": float((monthly > 0).mean()) if len(monthly) else np.nan,
            "best_month": float(monthly.max()) if len(monthly) else np.nan,
            "worst_month": float(monthly.min()) if len(monthly) else np.nan,
            "average_monthly_turnover": np.nan,
            "number_of_rebalances": np.nan,
            "average_number_of_holdings": np.nan,
        }
        if row["max_drawdown"] != 0 and not pd.isna(row["max_drawdown"]):
            row["calmar_ratio"] = row["cagr"] / abs(row["max_drawdown"])
        rows.append(row)

    summary = pd.DataFrame(rows).set_index("name")
    if rebalance_log is not None and not rebalance_log.empty and "Dual Momentum" in summary.index:
        summary.loc["Dual Momentum", "average_monthly_turnover"] = float(rebalance_log["turnover"].mean())
        summary.loc["Dual Momentum", "number_of_rebalances"] = int(len(rebalance_log))
        summary.loc["Dual Momentum", "average_number_of_holdings"] = float(rebalance_log["num_holdings"].mean())
    return summary
