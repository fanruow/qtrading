"""Market regime classification from trailing technical features."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import pandas as pd


class MarketRegime(str, Enum):
    BULLISH_TREND = "BULLISH_TREND"
    BEARISH_TREND = "BEARISH_TREND"
    RANGE_BOUND = "RANGE_BOUND"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"
    LOW_VOLATILITY = "LOW_VOLATILITY"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class RegimeResult:
    symbol: str
    regime: MarketRegime
    trend_score: float
    range_score: float
    volatility_score: float
    reasons: list[str]


class MarketRegimeClassifier:
    """Rule-based market regime classifier using only observed feature history."""

    required_columns = {
        "close",
        "sma_20",
        "sma_50",
        "rsi_14",
        "macd_hist",
        "atr_14",
        "rv_20",
    }

    def __init__(
        self,
        volatility_lookback: int = 60,
        range_close_threshold: float = 0.01,
        atr_compression_quantile: float = 0.35,
    ) -> None:
        if volatility_lookback <= 1:
            raise ValueError("volatility_lookback must be greater than 1")
        self.volatility_lookback = volatility_lookback
        self.range_close_threshold = range_close_threshold
        self.atr_compression_quantile = atr_compression_quantile

    def classify(self, symbol: str, features: pd.DataFrame) -> RegimeResult:
        """Classify the latest row using only current and prior feature values."""

        self._validate_features(features)
        usable = features.dropna(subset=list(self.required_columns))
        if usable.empty:
            return RegimeResult(
                symbol=symbol,
                regime=MarketRegime.UNKNOWN,
                trend_score=0.0,
                range_score=0.0,
                volatility_score=0.0,
                reasons=["Insufficient non-null feature history to classify regime."],
            )

        latest = usable.iloc[-1]
        history = usable.iloc[: len(usable)]
        close = float(latest["close"])
        sma_20 = float(latest["sma_20"])
        sma_50 = float(latest["sma_50"])
        rsi_14 = float(latest["rsi_14"])
        macd_hist = float(latest["macd_hist"])
        atr_14 = float(latest["atr_14"])
        rv_20 = float(latest["rv_20"])

        bullish = close > sma_20 > sma_50 and macd_hist > 0 and 50 <= rsi_14 <= 75
        bearish = close < sma_20 < sma_50 and macd_hist < 0 and rsi_14 < 50

        close_distance = abs(close - sma_20) / close if close != 0 else float("inf")
        atr_ratio = atr_14 / close if close != 0 else float("inf")
        atr_history_ratio = (history["atr_14"] / history["close"].replace(0, pd.NA)).dropna()
        atr_threshold = float(atr_history_ratio.quantile(self.atr_compression_quantile))
        range_bound = close_distance <= self.range_close_threshold and atr_ratio <= atr_threshold

        rv_history = history["rv_20"].dropna().tail(self.volatility_lookback)
        rv_75 = float(rv_history.quantile(0.75))
        rv_25 = float(rv_history.quantile(0.25))
        high_volatility = rv_20 > rv_75
        low_volatility = rv_20 < rv_25

        reasons: list[str] = []
        if bullish:
            reasons.append(
                "Bullish trend: close is above SMA20 and SMA50, MACD histogram is positive, "
                "and RSI14 is between 50 and 75."
            )
        if bearish:
            reasons.append(
                "Bearish trend: close is below SMA20 and SMA50, MACD histogram is negative, "
                "and RSI14 is below 50."
            )
        if range_bound:
            reasons.append(
                "Range-bound: close is near SMA20 and ATR14 is compressed versus recent history."
            )
        if high_volatility:
            reasons.append("High volatility: RV20 is above its trailing 75th percentile.")
        if low_volatility:
            reasons.append("Low volatility: RV20 is below its trailing 25th percentile.")

        trend_score = self._trend_score(bullish=bullish, bearish=bearish)
        range_score = self._range_score(close_distance=close_distance, atr_ratio=atr_ratio, atr_threshold=atr_threshold)
        volatility_score = self._volatility_score(rv_20=rv_20, rv_25=rv_25, rv_75=rv_75)

        if high_volatility:
            regime = MarketRegime.HIGH_VOLATILITY
        elif low_volatility:
            regime = MarketRegime.LOW_VOLATILITY
        elif bullish:
            regime = MarketRegime.BULLISH_TREND
        elif bearish:
            regime = MarketRegime.BEARISH_TREND
        elif range_bound:
            regime = MarketRegime.RANGE_BOUND
        else:
            regime = MarketRegime.UNKNOWN
            reasons.append("No configured regime rule matched the latest feature row.")

        return RegimeResult(
            symbol=symbol,
            regime=regime,
            trend_score=trend_score,
            range_score=range_score,
            volatility_score=volatility_score,
            reasons=reasons,
        )

    def _validate_features(self, features: pd.DataFrame) -> None:
        missing = sorted(self.required_columns - set(features.columns))
        if missing:
            raise ValueError(f"features missing required columns: {', '.join(missing)}")
        if features.empty:
            raise ValueError("features must not be empty")

    @staticmethod
    def _trend_score(bullish: bool, bearish: bool) -> float:
        if bullish:
            return 1.0
        if bearish:
            return -1.0
        return 0.0

    @staticmethod
    def _range_score(close_distance: float, atr_ratio: float, atr_threshold: float) -> float:
        if close_distance == float("inf") or atr_ratio == float("inf") or atr_threshold <= 0:
            return 0.0
        close_component = max(0.0, 1.0 - close_distance / 0.01)
        atr_component = max(0.0, 1.0 - atr_ratio / atr_threshold)
        return float((close_component + atr_component) / 2)

    @staticmethod
    def _volatility_score(rv_20: float, rv_25: float, rv_75: float) -> float:
        if rv_75 <= rv_25:
            return 0.0
        midpoint = (rv_25 + rv_75) / 2
        half_range = (rv_75 - rv_25) / 2
        return float((rv_20 - midpoint) / half_range)
