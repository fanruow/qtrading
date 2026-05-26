"""Rule-based market regime classification."""

from __future__ import annotations

from enum import Enum

import pandas as pd


class MarketRegime(str, Enum):
    BULLISH_TREND = "bullish_trend"
    BEARISH_TREND = "bearish_trend"
    RANGE_BOUND = "range_bound"
    HIGH_VOLATILITY = "high_volatility"
    LOW_VOLATILITY = "low_volatility"


def classify_market_regime(features: pd.DataFrame) -> MarketRegime:
    latest = features.dropna().iloc[-1]
    vol = float(latest.get("realized_vol_21", 0.0))
    rsi_value = float(latest.get("rsi_14", 50.0))
    close = float(latest["close"])
    sma_20 = float(latest.get("sma_20", close))
    sma_50 = float(latest.get("sma_50", close))

    if vol >= 0.35:
        return MarketRegime.HIGH_VOLATILITY
    if vol <= 0.12:
        return MarketRegime.LOW_VOLATILITY
    if close > sma_20 > sma_50 and rsi_value >= 50:
        return MarketRegime.BULLISH_TREND
    if close < sma_20 < sma_50 and rsi_value <= 50:
        return MarketRegime.BEARISH_TREND
    return MarketRegime.RANGE_BOUND
