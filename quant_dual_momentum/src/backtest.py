"""Backtest engine for monthly ETF dual momentum."""

from __future__ import annotations

import pandas as pd

from .data import compute_daily_returns
from .portfolio import (
    apply_volatility_scale,
    calculate_realized_volatility,
    calculate_transaction_cost,
    calculate_turnover,
    calculate_volatility_scale,
)
from .signals import generate_raw_signal_weights, map_signal_dates_to_execution_dates


def simulate_weights_from_rebalance_schedule(
    returns: pd.DataFrame,
    rebalance_weights: pd.DataFrame,
) -> pd.DataFrame:
    """Expand sparse rebalance weights to daily weights used for returns.

    Weights listed on an execution date are used for that execution day's
    close-to-close return. Dates before the first execution hold cash.
    """
    daily_weights = rebalance_weights.reindex(returns.index).ffill().fillna(0.0)
    return daily_weights.reindex(columns=returns.columns, fill_value=0.0)


def run_dual_momentum_backtest(
    prices: pd.DataFrame,
    top_n: int = 3,
    target_volatility: float = 0.10,
    vol_window: int = 63,
    transaction_cost_rate: float = 0.001,
    short_lag: int = 21,
    long_lag: int = 252,
    ma_window: int = 200,
) -> dict[str, pd.DataFrame | pd.Series]:
    """Run dual momentum backtest with next-day execution and vol targeting."""
    returns = compute_daily_returns(prices).fillna(0.0)
    raw_signal_weights = generate_raw_signal_weights(
        prices=prices,
        top_n=top_n,
        short_lag=short_lag,
        long_lag=long_lag,
        ma_window=ma_window,
    )
    signal_to_execution = map_signal_dates_to_execution_dates(raw_signal_weights.index, returns.index)

    rebalance_weights = pd.DataFrame(columns=returns.columns, dtype=float)
    rebalance_records: list[dict[str, object]] = []
    strategy_returns = pd.Series(0.0, index=returns.index, name="Dual Momentum")
    current_weights = pd.Series(0.0, index=returns.columns)

    execution_to_signal = {execution: signal for signal, execution in signal_to_execution.items()}

    for date in returns.index:
        if date in execution_to_signal:
            signal_date = execution_to_signal[date]
            raw_weights = raw_signal_weights.loc[signal_date]
            realized_vol = calculate_realized_volatility(strategy_returns.loc[: signal_date], vol_window).loc[signal_date]
            scale = calculate_volatility_scale(
                pd.Series([realized_vol], index=[signal_date]),
                target_volatility=target_volatility,
            ).iloc[0]
            new_weights = apply_volatility_scale(raw_weights, scale).reindex(returns.columns).fillna(0.0)
            turnover = calculate_turnover(new_weights, current_weights)
            cost = calculate_transaction_cost(turnover, transaction_cost_rate) if turnover > 0 else 0.0
            current_weights = new_weights
            rebalance_weights.loc[date] = current_weights
            rebalance_records.append(
                {
                    "signal_date": signal_date,
                    "execution_date": date,
                    "scale": 1.0 if pd.isna(scale) else float(scale),
                    "realized_vol": realized_vol,
                    "turnover": turnover,
                    "cost": cost,
                    "cash_weight": 1.0 - float(current_weights.sum()),
                    "num_holdings": int((current_weights > 1e-12).sum()),
                }
            )
        else:
            cost = 0.0

        strategy_returns.loc[date] = float((current_weights * returns.loc[date]).sum() - cost)

    weights = simulate_weights_from_rebalance_schedule(returns, rebalance_weights)
    equity = (1.0 + strategy_returns).cumprod()
    equity.name = "Dual Momentum"
    rebalance_log = pd.DataFrame(rebalance_records)
    if not rebalance_log.empty:
        rebalance_log = rebalance_log.set_index("execution_date", drop=False)
    return {
        "returns": strategy_returns,
        "equity": equity,
        "weights": weights,
        "rebalance_weights": rebalance_weights,
        "rebalance_log": rebalance_log,
        "raw_signal_weights": raw_signal_weights,
    }
