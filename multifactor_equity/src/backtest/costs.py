from __future__ import annotations

import pandas as pd


def calculate_turnover(new_weights: pd.Series, old_weights: pd.Series) -> float:
    idx = new_weights.index.union(old_weights.index)
    return float((new_weights.reindex(idx, fill_value=0.0) - old_weights.reindex(idx, fill_value=0.0)).abs().sum())


def trading_cost(turnover: float, commission_rate: float = 0.001, slippage_rate: float = 0.001) -> dict[str, float]:
    commission = turnover * commission_rate
    slippage = turnover * slippage_rate
    return {"commission_cost": commission, "slippage_cost": slippage, "total_cost": commission + slippage}
