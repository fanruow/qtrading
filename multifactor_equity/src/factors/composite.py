from __future__ import annotations

import pandas as pd

from src.factors.low_vol import low_vol_score
from src.factors.momentum import momentum_score
from src.factors.quality import quality_score
from src.factors.value import value_score


def compute_factor_scores(as_of: pd.Timestamp, close: pd.DataFrame, universe: pd.DataFrame, config: dict) -> pd.DataFrame:
    if universe.empty:
        return pd.DataFrame()
    lower = config["factors"]["winsor_lower"]
    upper = config["factors"]["winsor_upper"]
    max_missing = config["factors"]["max_missing_subfactors"]
    parts = [
        momentum_score(as_of, close, universe, lower, upper),
        quality_score(universe, lower, upper, max_missing),
        value_score(universe, lower, upper, max_missing),
        low_vol_score(as_of, close, universe, config["data"].get("benchmark", "SPY"), lower, upper, max_missing),
    ]
    scores = universe[["sector"]].copy()
    for part in parts:
        scores = scores.join(part, how="left")
    weights = config["factors"]["weights"]
    score_cols = list(weights)
    scores["missing_count"] = scores[[c for c in scores.columns if c.endswith("_missing_count")]].sum(axis=1)
    scores["composite_score"] = sum(scores[col] * weight for col, weight in weights.items())
    scores = scores.dropna(subset=score_cols + ["composite_score"])
    scores["ticker"] = scores.index
    scores["signal_date"] = pd.Timestamp(as_of)
    return scores
