"""ML feature dataset construction and meta-labeling utilities."""

from __future__ import annotations

import pandas as pd

from src.features.technical import build_technical_features


def build_feature_dataset(prices: pd.DataFrame, horizon: int = 5) -> pd.DataFrame:
    """Build supervised features with forward return labels."""

    features = build_technical_features(prices)
    features["forward_return"] = prices["close"].pct_change(horizon).shift(-horizon)
    features["direction_label"] = (features["forward_return"] > 0).astype(int)
    return features.dropna()


def build_meta_labels(
    predictions: pd.Series,
    realized_returns: pd.Series,
    profit_threshold: float = 0.0,
) -> pd.Series:
    """Label whether a primary model signal would have been profitable."""

    aligned = pd.concat([predictions.rename("prediction"), realized_returns.rename("return")], axis=1).dropna()
    profitable = aligned["prediction"].where(aligned["prediction"] != 0, 1) * aligned["return"]
    return (profitable > profit_threshold).astype(int)
