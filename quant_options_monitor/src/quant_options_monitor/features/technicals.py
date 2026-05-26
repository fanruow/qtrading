"""Technical indicators built from historical OHLCV data only."""

from __future__ import annotations

import numpy as np
import pandas as pd


def _validate_window(window: int) -> None:
    if window <= 0:
        raise ValueError("window must be positive")


def sma(series: pd.Series, window: int) -> pd.Series:
    """Simple moving average aligned to the input index."""

    _validate_window(window)
    return series.rolling(window=window, min_periods=window).mean()


def ema(series: pd.Series, window: int) -> pd.Series:
    """Exponential moving average aligned to the input index."""

    _validate_window(window)
    return series.ewm(span=window, adjust=False, min_periods=window).mean()


def rsi(close: pd.Series, window: int = 14) -> pd.Series:
    """Relative Strength Index using rolling average gains and losses."""

    _validate_window(window)
    delta = close.diff()
    gains = delta.clip(lower=0)
    losses = -delta.clip(upper=0)
    avg_gain = gains.rolling(window=window, min_periods=window).mean()
    avg_loss = losses.rolling(window=window, min_periods=window).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    result = 100 - (100 / (1 + rs))
    result = result.mask((avg_loss == 0) & (avg_gain > 0), 100.0)
    result = result.mask((avg_gain == 0) & (avg_loss > 0), 0.0)
    result = result.mask((avg_gain == 0) & (avg_loss == 0), 50.0)
    return result


def macd(
    close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Moving Average Convergence Divergence line, signal line, and histogram."""

    _validate_window(fast)
    _validate_window(slow)
    _validate_window(signal)
    if fast >= slow:
        raise ValueError("fast must be smaller than slow")

    macd_line = ema(close, fast) - ema(close, slow)
    signal_line = macd_line.ewm(span=signal, adjust=False, min_periods=signal).mean()
    hist = macd_line - signal_line
    return macd_line, signal_line, hist


def atr(high: pd.Series, low: pd.Series, close: pd.Series, window: int = 14) -> pd.Series:
    """Average True Range aligned to the input index."""

    _validate_window(window)
    previous_close = close.shift(1)
    true_range = pd.concat(
        [
            high - low,
            (high - previous_close).abs(),
            (low - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return true_range.rolling(window=window, min_periods=window).mean()


def realized_volatility(
    close: pd.Series, window: int = 20, annualization: int = 252
) -> pd.Series:
    """Annualized rolling standard deviation of daily close-to-close returns."""

    _validate_window(window)
    if annualization <= 0:
        raise ValueError("annualization must be positive")
    returns = close.pct_change()
    return returns.rolling(window=window, min_periods=window).std() * np.sqrt(annualization)


def volume_zscore(volume: pd.Series, window: int = 20) -> pd.Series:
    """Rolling z-score of volume."""

    _validate_window(window)
    mean = volume.rolling(window=window, min_periods=window).mean()
    std = volume.rolling(window=window, min_periods=window).std()
    return (volume - mean) / std.replace(0, np.nan)


def rolling_return(close: pd.Series, window: int) -> pd.Series:
    """Trailing percentage return over `window` periods."""

    _validate_window(window)
    return close.pct_change(periods=window)
