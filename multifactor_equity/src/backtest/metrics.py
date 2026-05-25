from __future__ import annotations

import numpy as np
import pandas as pd


def drawdown(equity: pd.Series) -> pd.Series:
    return equity / equity.cummax() - 1


def performance_metrics(
    daily_returns: pd.Series,
    equity: pd.Series,
    turnover: pd.Series | None = None,
    holdings: pd.Series | None = None,
    sector_exposure: pd.DataFrame | None = None,
    benchmark_returns: pd.Series | None = None,
) -> pd.Series:
    total_return = equity.iloc[-1] / equity.iloc[0] - 1
    years = max((equity.index[-1] - equity.index[0]).days / 365.25, 1 / 252)
    cagr = (1 + total_return) ** (1 / years) - 1
    ann_vol = daily_returns.std() * np.sqrt(252)
    sharpe = daily_returns.mean() / daily_returns.std() * np.sqrt(252) if daily_returns.std() else np.nan
    downside = daily_returns[daily_returns < 0].std() * np.sqrt(252)
    sortino = cagr / downside if downside else np.nan
    max_dd = drawdown(equity).min()
    monthly = (1 + daily_returns).resample("ME").prod() - 1
    bench_monthly = None if benchmark_returns is None else ((1 + benchmark_returns).resample("ME").prod() - 1)
    active = None if benchmark_returns is None else daily_returns.sub(benchmark_returns, fill_value=0.0)
    info = active.mean() / active.std() * np.sqrt(252) if active is not None and active.std() else np.nan
    hit = (monthly > bench_monthly.reindex(monthly.index)).mean() if bench_monthly is not None else np.nan
    avg_sector_exposure = sector_exposure.drop(columns=["date"], errors="ignore").mean().mean() if sector_exposure is not None and not sector_exposure.empty else np.nan
    return pd.Series(
        {
            "total_return": total_return,
            "cagr": cagr,
            "annualized_volatility": ann_vol,
            "sharpe_ratio": sharpe,
            "sortino_ratio": sortino,
            "max_drawdown": max_dd,
            "calmar_ratio": cagr / abs(max_dd) if max_dd else np.nan,
            "monthly_win_rate": (monthly > 0).mean(),
            "average_monthly_turnover": turnover.mean() if turnover is not None and len(turnover) else 0.0,
            "average_number_of_holdings": holdings.mean() if holdings is not None and len(holdings) else 0.0,
            "average_sector_exposure": avg_sector_exposure,
            "best_month": monthly.max() if len(monthly) else np.nan,
            "worst_month": monthly.min() if len(monthly) else np.nan,
            "hit_rate_vs_spy_by_month": hit,
            "information_ratio_vs_spy": info,
        }
    )
