"""Portfolio construction, turnover, and volatility targeting."""

from __future__ import annotations

import numpy as np
import pandas as pd


def calculate_turnover(new_weights: pd.Series, old_weights: pd.Series) -> float:
    """Calculate one-way turnover as sum(abs(new_weight - old_weight))."""
    aligned_new, aligned_old = new_weights.align(old_weights, fill_value=0.0)
    return float((aligned_new - aligned_old).abs().sum())


def calculate_transaction_cost(turnover: float, cost_rate: float = 0.001) -> float:
    """Calculate transaction cost as turnover multiplied by cost rate."""
    return float(turnover * cost_rate)


def calculate_realized_volatility(
    returns: pd.Series,
    window: int = 63,
    annualization: int = 252,
) -> pd.Series:
    """Calculate annualized rolling realized volatility."""
    return returns.rolling(window=window, min_periods=window).std() * np.sqrt(annualization)


def calculate_volatility_scale(
    realized_volatility: pd.Series,
    target_volatility: float = 0.10,
) -> pd.Series:
    """Convert realized volatility into a clipped volatility-target scale."""
    scale = target_volatility / realized_volatility
    scale = scale.replace([np.inf, -np.inf], np.nan)
    return scale.clip(lower=0.0, upper=1.0)


def apply_volatility_scale(raw_weights: pd.Series, scale: float) -> pd.Series:
    """Apply scalar volatility target scale to raw risky-asset weights."""
    if pd.isna(scale):
        scale = 1.0
    return raw_weights * float(np.clip(scale, 0.0, 1.0))


def average_number_of_holdings(weights: pd.DataFrame) -> float:
    """Calculate average number of non-zero risky holdings."""
    if weights.empty:
        return 0.0
    return float((weights > 1e-12).sum(axis=1).mean())
