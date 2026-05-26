from __future__ import annotations

import pandas as pd

from src.data.providers import SyntheticMarketDataProvider
from src.features.technical import build_technical_features, rsi


def test_rsi_bounds() -> None:
    series = pd.Series([1, 2, 3, 2, 4, 5, 6, 5, 7, 8, 9, 10, 9, 11, 12, 13], dtype=float)
    values = rsi(series).dropna()
    assert ((values >= 0) & (values <= 100)).all()


def test_build_technical_features_contains_required_columns() -> None:
    prices = SyntheticMarketDataProvider().get_price_history("SPY")
    features = build_technical_features(prices)
    assert {"sma_20", "ema_20", "rsi_14", "macd", "atr_14", "realized_vol_21", "volume_zscore_20"} <= set(
        features.columns
    )
