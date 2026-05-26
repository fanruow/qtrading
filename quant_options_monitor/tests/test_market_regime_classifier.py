from __future__ import annotations

import pandas as pd
import pytest

from quant_options_monitor.features.regime import MarketRegime, MarketRegimeClassifier


def feature_frame(
    *,
    close: float,
    sma_20: float,
    sma_50: float,
    rsi_14: float,
    macd_hist: float,
    atr_14: float,
    rv_20: float,
    rows: int = 80,
) -> pd.DataFrame:
    index = pd.date_range("2024-01-01", periods=rows, freq="B")
    frame = pd.DataFrame(
        {
            "close": [100.0] * rows,
            "sma_20": [100.0] * rows,
            "sma_50": [100.0] * rows,
            "rsi_14": [50.0] * rows,
            "macd_hist": [0.0] * rows,
            "atr_14": [2.0] * rows,
            "rv_20": [0.20] * rows,
        },
        index=index,
    )
    frame["rv_20"] = [0.15 + i * 0.001 for i in range(rows)]
    frame.loc[index[-1], ["close", "sma_20", "sma_50", "rsi_14", "macd_hist", "atr_14", "rv_20"]] = [
        close,
        sma_20,
        sma_50,
        rsi_14,
        macd_hist,
        atr_14,
        rv_20,
    ]
    return frame


def test_classifier_detects_bullish_trend_with_reasons() -> None:
    features = feature_frame(
        close=110.0,
        sma_20=105.0,
        sma_50=100.0,
        rsi_14=62.0,
        macd_hist=0.5,
        atr_14=2.0,
        rv_20=0.20,
    )

    result = MarketRegimeClassifier().classify("SPY", features)

    assert result.symbol == "SPY"
    assert result.regime == MarketRegime.BULLISH_TREND
    assert result.trend_score == 1.0
    assert any("Bullish trend" in reason for reason in result.reasons)


def test_classifier_detects_bearish_trend_with_reasons() -> None:
    features = feature_frame(
        close=90.0,
        sma_20=95.0,
        sma_50=100.0,
        rsi_14=42.0,
        macd_hist=-0.5,
        atr_14=2.0,
        rv_20=0.20,
    )

    result = MarketRegimeClassifier().classify("QQQ", features)

    assert result.regime == MarketRegime.BEARISH_TREND
    assert result.trend_score == -1.0
    assert any("Bearish trend" in reason for reason in result.reasons)


def test_classifier_detects_range_bound_with_compressed_atr() -> None:
    features = feature_frame(
        close=100.2,
        sma_20=100.0,
        sma_50=99.5,
        rsi_14=52.0,
        macd_hist=0.0,
        atr_14=0.5,
        rv_20=0.20,
    )

    result = MarketRegimeClassifier().classify("IWM", features)

    assert result.regime == MarketRegime.RANGE_BOUND
    assert result.range_score > 0
    assert any("Range-bound" in reason for reason in result.reasons)


def test_classifier_detects_high_and_low_volatility_against_trailing_percentiles() -> None:
    classifier = MarketRegimeClassifier()

    high = classifier.classify(
        "TSLA",
        feature_frame(
            close=100.0,
            sma_20=100.0,
            sma_50=100.0,
            rsi_14=50.0,
            macd_hist=0.0,
            atr_14=2.0,
            rv_20=0.40,
        ),
    )
    low = classifier.classify(
        "TLT",
        feature_frame(
            close=100.0,
            sma_20=100.0,
            sma_50=100.0,
            rsi_14=50.0,
            macd_hist=0.0,
            atr_14=2.0,
            rv_20=0.10,
        ),
    )

    assert high.regime == MarketRegime.HIGH_VOLATILITY
    assert any("High volatility" in reason for reason in high.reasons)
    assert low.regime == MarketRegime.LOW_VOLATILITY
    assert any("Low volatility" in reason for reason in low.reasons)


def test_classifier_does_not_use_future_rows() -> None:
    features = feature_frame(
        close=110.0,
        sma_20=105.0,
        sma_50=100.0,
        rsi_14=62.0,
        macd_hist=0.5,
        atr_14=2.0,
        rv_20=0.20,
    )
    as_of_features = features.iloc[:-1].copy()
    mutated_future = features.copy()
    mutated_future.iloc[-1] = [1.0, 500.0, 700.0, 5.0, -99.0, 99.0, 9.0]

    classifier = MarketRegimeClassifier()

    baseline = classifier.classify("SPY", as_of_features)
    with_future_changed = classifier.classify("SPY", mutated_future.iloc[:-1])

    assert baseline == with_future_changed


def test_classifier_requires_expected_columns() -> None:
    features = feature_frame(
        close=100.0,
        sma_20=100.0,
        sma_50=100.0,
        rsi_14=50.0,
        macd_hist=0.0,
        atr_14=2.0,
        rv_20=0.20,
    ).drop(columns=["rv_20"])

    with pytest.raises(ValueError, match="features missing required columns: rv_20"):
        MarketRegimeClassifier().classify("SPY", features)
