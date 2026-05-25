from __future__ import annotations

import pandas as pd

from src.portfolio.construction import construct_portfolio


def build_target_weights(signal_scores: pd.DataFrame, portfolio_config: dict) -> pd.Series:
    return construct_portfolio(
        signal_scores,
        portfolio_config["top_n"],
        portfolio_config["max_stock_weight"],
        portfolio_config["max_sector_weight"],
    )
