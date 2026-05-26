from __future__ import annotations

import pandas as pd
import pytest

from quant_options_monitor.strategies.equity_signal import (
    EquitySignalEngine,
    EquitySignalType,
)


def feature_frame(
    *,
    close: float,
    sma_20: float,
    sma_50: float,
    macd_hist: float,
    rsi_14: float,
    volume_zscore_20: float,
    rows: int = 30,
) -> pd.DataFrame:
    index = pd.date_range("2024-01-01", periods=rows, freq="B")
    frame = pd.DataFrame(
        {
            "close": [100.0] * rows,
            "sma_20": [100.0] * rows,
            "sma_50": [100.0] * rows,
            "macd_hist": [0.0] * rows,
            "rsi_14": [50.0] * rows,
            "volume_zscore_20": [0.0] * rows,
        },
        index=index,
    )
    frame.loc[index[-1], ["close", "sma_20", "sma_50", "macd_hist", "rsi_14", "volume_zscore_20"]] = [
        close,
        sma_20,
        sma_50,
        macd_hist,
        rsi_14,
        volume_zscore_20,
    ]
    return frame


def test_equity_signal_buy_bias_with_human_reasons() -> None:
    signal = EquitySignalEngine().generate(
        "spy",
        feature_frame(
            close=110.0,
            sma_20=105.0,
            sma_50=100.0,
            macd_hist=0.7,
            rsi_14=62.0,
            volume_zscore_20=1.2,
        ),
    )

    assert signal.symbol == "SPY"
    assert signal.signal_type == EquitySignalType.BUY_BIAS.value
    assert signal.score == 100.0
    assert signal.confidence == 1.0
    assert any("close is above SMA20" in reason for reason in signal.reasons)


def test_equity_signal_sell_bias_with_human_reasons() -> None:
    signal = EquitySignalEngine().generate(
        "QQQ",
        feature_frame(
            close=90.0,
            sma_20=95.0,
            sma_50=100.0,
            macd_hist=-0.5,
            rsi_14=42.0,
            volume_zscore_20=-0.2,
        ),
    )

    assert signal.signal_type == EquitySignalType.SELL_BIAS.value
    assert signal.score == -100.0
    assert signal.confidence == 1.0
    assert any("MACD histogram is negative" in reason for reason in signal.reasons)


def test_equity_signal_neutral_when_rules_do_not_fully_match() -> None:
    signal = EquitySignalEngine().generate(
        "NVDA",
        feature_frame(
            close=103.0,
            sma_20=102.0,
            sma_50=101.0,
            macd_hist=0.3,
            rsi_14=78.0,
            volume_zscore_20=1.0,
        ),
    )

    assert signal.signal_type == EquitySignalType.NEUTRAL.value
    assert 0 <= signal.confidence <= 1
    assert any("not fully satisfied" in reason for reason in signal.reasons)


def test_equity_signal_does_not_use_future_rows() -> None:
    features = feature_frame(
        close=110.0,
        sma_20=105.0,
        sma_50=100.0,
        macd_hist=0.7,
        rsi_14=62.0,
        volume_zscore_20=1.2,
    )
    as_of_features = features.iloc[:-1].copy()
    mutated_future = features.copy()
    mutated_future.iloc[-1] = [1.0, 500.0, 700.0, -99.0, 5.0, -5.0]

    engine = EquitySignalEngine()

    baseline = engine.generate("SPY", as_of_features)
    with_future_changed = engine.generate("SPY", mutated_future.iloc[:-1])

    assert baseline == with_future_changed


def test_equity_signal_missing_columns_raise_predictably() -> None:
    features = feature_frame(
        close=100.0,
        sma_20=100.0,
        sma_50=100.0,
        macd_hist=0.0,
        rsi_14=50.0,
        volume_zscore_20=0.0,
    ).drop(columns=["volume_zscore_20"])

    with pytest.raises(ValueError, match="features missing required columns: volume_zscore_20"):
        EquitySignalEngine().generate("SPY", features)
