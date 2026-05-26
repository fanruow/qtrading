"""Volatility and option-chain derived features."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.data.models import OptionContract


def iv_rank(current_iv: float, iv_history: pd.Series) -> float:
    low = float(iv_history.min())
    high = float(iv_history.max())
    if high <= low:
        return 0.0
    return float((current_iv - low) / (high - low))


def iv_percentile(current_iv: float, iv_history: pd.Series) -> float:
    history = iv_history.dropna()
    if history.empty:
        return 0.0
    return float((history <= current_iv).mean())


def iv_realized_spread(current_iv: float, realized_vol: float) -> float:
    return float(current_iv - realized_vol)


def term_structure_score(front_iv: float, back_iv: float) -> float:
    if back_iv <= 0:
        return 0.0
    return float((back_iv - front_iv) / back_iv)


def skew_score(chain: list[OptionContract]) -> float:
    calls = [c.implied_volatility for c in chain if c.right == "call" and c.implied_volatility]
    puts = [c.implied_volatility for c in chain if c.right == "put" and c.implied_volatility]
    if not calls or not puts:
        return 0.0
    return float(np.mean(puts) - np.mean(calls))


def summarize_chain_volatility(
    chain: list[OptionContract], realized_vol: float, iv_history: pd.Series | None = None
) -> dict[str, float]:
    ivs = pd.Series([c.implied_volatility for c in chain if c.implied_volatility])
    current_iv = float(ivs.median()) if not ivs.empty else 0.0
    history = iv_history if iv_history is not None else ivs
    return {
        "current_iv": current_iv,
        "iv_rank": iv_rank(current_iv, history),
        "iv_percentile": iv_percentile(current_iv, history),
        "iv_realized_spread": iv_realized_spread(current_iv, realized_vol),
        "skew_score": skew_score(chain),
    }
