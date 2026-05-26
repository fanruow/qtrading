"""Equity directional bias signal engine."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, field_validator


class EquitySignalType(str, Enum):
    BUY_BIAS = "BUY_BIAS"
    SELL_BIAS = "SELL_BIAS"
    NEUTRAL = "NEUTRAL"


class EquitySignal(BaseModel):
    """Alert-ready equity signal result."""

    model_config = ConfigDict(use_enum_values=True)

    symbol: str
    signal_type: EquitySignalType
    score: float = Field(ge=-100, le=100)
    confidence: float = Field(ge=0, le=1)
    reasons: list[str]
    timestamp: datetime

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        value = value.strip().upper()
        if not value:
            raise ValueError("symbol must not be empty")
        return value


class EquitySignalEngine:
    """Classifies latest trailing technical features into BUY/SELL/NEUTRAL bias."""

    required_columns = {
        "close",
        "sma_20",
        "sma_50",
        "macd_hist",
        "rsi_14",
        "volume_zscore_20",
    }

    def generate(self, symbol: str, features: pd.DataFrame) -> EquitySignal:
        """Generate an equity signal using the latest valid feature row only."""

        self._validate_features(features)
        usable = features.dropna(subset=list(self.required_columns))
        if usable.empty:
            return EquitySignal(
                symbol=symbol,
                signal_type=EquitySignalType.NEUTRAL,
                score=0.0,
                confidence=0.0,
                reasons=["Insufficient non-null technical features to form an equity bias."],
                timestamp=datetime.now(timezone.utc),
            )

        latest = usable.iloc[-1]
        timestamp = self._timestamp_from_index(usable.index[-1])

        buy_checks = {
            "close > SMA20 > SMA50": latest["close"] > latest["sma_20"] > latest["sma_50"],
            "MACD histogram > 0": latest["macd_hist"] > 0,
            "RSI14 between 50 and 70": 50 <= latest["rsi_14"] <= 70,
            "volume z-score > 0": latest["volume_zscore_20"] > 0,
        }
        sell_checks = {
            "close < SMA20 < SMA50": latest["close"] < latest["sma_20"] < latest["sma_50"],
            "MACD histogram < 0": latest["macd_hist"] < 0,
            "RSI14 < 50": latest["rsi_14"] < 50,
        }

        if all(buy_checks.values()):
            return EquitySignal(
                symbol=symbol,
                signal_type=EquitySignalType.BUY_BIAS,
                score=100.0,
                confidence=1.0,
                reasons=[
                    "BUY_BIAS: close is above SMA20 and SMA50.",
                    "BUY_BIAS: MACD histogram is positive.",
                    "BUY_BIAS: RSI14 is between 50 and 70.",
                    "BUY_BIAS: volume z-score is positive.",
                ],
                timestamp=timestamp,
            )

        if all(sell_checks.values()):
            return EquitySignal(
                symbol=symbol,
                signal_type=EquitySignalType.SELL_BIAS,
                score=-100.0,
                confidence=1.0,
                reasons=[
                    "SELL_BIAS: close is below SMA20 and SMA50.",
                    "SELL_BIAS: MACD histogram is negative.",
                    "SELL_BIAS: RSI14 is below 50.",
                ],
                timestamp=timestamp,
            )

        buy_score = sum(buy_checks.values()) / len(buy_checks)
        sell_score = sum(sell_checks.values()) / len(sell_checks)
        confidence = max(buy_score, sell_score)
        score = float(round((buy_score - sell_score) * 100, 4))
        return EquitySignal(
            symbol=symbol,
            signal_type=EquitySignalType.NEUTRAL,
            score=score,
            confidence=float(round(confidence, 4)),
            reasons=[
                "NEUTRAL: configured BUY_BIAS and SELL_BIAS rules are not fully satisfied.",
                f"BUY_BIAS checks passed: {sum(buy_checks.values())}/{len(buy_checks)}.",
                f"SELL_BIAS checks passed: {sum(sell_checks.values())}/{len(sell_checks)}.",
            ],
            timestamp=timestamp,
        )

    def _validate_features(self, features: pd.DataFrame) -> None:
        if features.empty:
            raise ValueError("features must not be empty")
        missing = sorted(self.required_columns - set(features.columns))
        if missing:
            raise ValueError(f"features missing required columns: {', '.join(missing)}")

    @staticmethod
    def _timestamp_from_index(index_value: object) -> datetime:
        if isinstance(index_value, pd.Timestamp):
            timestamp = index_value.to_pydatetime()
        elif isinstance(index_value, datetime):
            timestamp = index_value
        else:
            return datetime.now(timezone.utc)
        if timestamp.tzinfo is None:
            return timestamp.replace(tzinfo=timezone.utc)
        return timestamp.astimezone(timezone.utc)
