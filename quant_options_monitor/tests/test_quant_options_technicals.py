from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from quant_options_monitor.features.pipeline import build_technical_features
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


def deterministic_ohlcv(rows: int = 240) -> pd.DataFrame:
    index = pd.date_range("2024-01-01", periods=rows, freq="B")
    base = pd.Series(np.arange(rows, dtype=float), index=index)
    close = 100.0 + base * 0.5 + np.sin(base / 5.0)
    return pd.DataFrame(
        {
            "open": close - 0.25,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "volume": 1_000_000 + (base % 10) * 10_000,
        },
        index=index,
    )


def assert_aligned(series: pd.Series, index: pd.Index) -> None:
    assert isinstance(series, pd.Series)
    assert series.index.equals(index)
    assert len(series) == len(index)


def test_indicator_series_are_aligned_and_warmup_nan_is_predictable() -> None:
    data = deterministic_ohlcv(80)
    close = data["close"]

    indicators = [
        sma(close, 20),
        ema(close, 20),
        rsi(close, 14),
        atr(data["high"], data["low"], close, 14),
        realized_volatility(close, 20),
        volume_zscore(data["volume"], 20),
        rolling_return(close, 5),
    ]

    for series in indicators:
        assert_aligned(series, data.index)

    assert sma(close, 20).iloc[:19].isna().all()
    assert pd.isna(sma(close, 20).iloc[18])
    assert not pd.isna(sma(close, 20).iloc[19])
    assert rolling_return(close, 5).iloc[:5].isna().all()
    assert not pd.isna(rolling_return(close, 5).iloc[5])


def test_macd_returns_aligned_components() -> None:
    data = deterministic_ohlcv(120)

    macd_line, signal_line, hist = macd(data["close"])

    assert_aligned(macd_line, data.index)
    assert_aligned(signal_line, data.index)
    assert_aligned(hist, data.index)
    pd.testing.assert_series_equal(hist, macd_line - signal_line)


def test_build_technical_features_adds_expected_columns() -> None:
    data = deterministic_ohlcv()

    features = build_technical_features(data)

    expected = {
        "sma_20",
        "sma_50",
        "sma_200",
        "ema_20",
        "rsi_14",
        "macd",
        "macd_signal",
        "macd_hist",
        "atr_14",
        "rv_10",
        "rv_20",
        "volume_zscore_20",
        "return_1d",
        "return_5d",
        "return_20d",
    }
    assert expected <= set(features.columns)
    assert features.index.equals(data.index)
    assert features["sma_200"].iloc[:199].isna().all()
    assert not pd.isna(features["sma_200"].iloc[199])


def test_build_technical_features_has_no_lookahead_bias_for_trailing_features() -> None:
    data = deterministic_ohlcv(80)
    changed_future = data.copy()
    changed_future.loc[changed_future.index[-1], "close"] *= 10
    changed_future.loc[changed_future.index[-1], "high"] *= 10
    changed_future.loc[changed_future.index[-1], "low"] *= 10
    changed_future.loc[changed_future.index[-1], "volume"] *= 10

    baseline = build_technical_features(data)
    modified = build_technical_features(changed_future)

    pd.testing.assert_frame_equal(baseline.iloc[:-1], modified.iloc[:-1])


def test_build_technical_features_missing_columns_raise_predictably() -> None:
    data = deterministic_ohlcv().drop(columns=["volume"])

    with pytest.raises(ValueError, match="missing required columns: volume"):
        build_technical_features(data)


def test_invalid_windows_raise_value_error() -> None:
    with pytest.raises(ValueError, match="window must be positive"):
        sma(pd.Series([1.0, 2.0]), 0)
