"""Feature pipeline for normalized OHLCV frames."""

from __future__ import annotations

import pandas as pd

from quant_options_monitor.features.technicals import (
    atr,
    ema,
    macd,
    realized_volatility,
    rolling_return,
    rsi,
    sma,
    volume_zscore,
)


_REQUIRED_COLUMNS = {"open", "high", "low", "close", "volume"}


def build_technical_features(ohlcv: pd.DataFrame) -> pd.DataFrame:
    """Return OHLCV data with deterministic, trailing technical features added."""

    missing = sorted(_REQUIRED_COLUMNS - set(ohlcv.columns))
    if missing:
        raise ValueError(f"OHLCV data is missing required columns: {', '.join(missing)}")

    features = ohlcv.copy()
    close = features["close"]
    high = features["high"]
    low = features["low"]
    volume = features["volume"]

    features["sma_20"] = sma(close, 20)
    features["sma_50"] = sma(close, 50)
    features["sma_200"] = sma(close, 200)
    features["ema_20"] = ema(close, 20)
    features["rsi_14"] = rsi(close, 14)

    macd_line, macd_signal, macd_hist = macd(close)
    features["macd"] = macd_line
    features["macd_signal"] = macd_signal
    features["macd_hist"] = macd_hist

    features["atr_14"] = atr(high, low, close, 14)
    features["rv_10"] = realized_volatility(close, 10)
    features["rv_20"] = realized_volatility(close, 20)
    features["volume_zscore_20"] = volume_zscore(volume, 20)
    features["return_1d"] = rolling_return(close, 1)
    features["return_5d"] = rolling_return(close, 5)
    features["return_20d"] = rolling_return(close, 20)
    return features
