from __future__ import annotations

from dataclasses import dataclass


SCORE_COLUMNS = ["momentum_score", "value_score", "quality_score", "low_vol_score"]


@dataclass(frozen=True)
class DecisionConfig:
    min_weight_change: float
    min_trade_notional: float
    allow_fractional_shares: bool
    portfolio_value: float
