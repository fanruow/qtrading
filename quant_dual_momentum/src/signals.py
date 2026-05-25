"""Signal and indicator calculations for dual momentum."""

from __future__ import annotations

import pandas as pd


def calculate_12_1_momentum(
    prices: pd.DataFrame,
    short_lag: int = 21,
    long_lag: int = 252,
) -> pd.DataFrame:
    """Calculate 12-1 momentum as price[t-short_lag] / price[t-long_lag] - 1."""
    return prices.shift(short_lag) / prices.shift(long_lag) - 1.0


def calculate_moving_average(prices: pd.DataFrame, window: int = 200) -> pd.DataFrame:
    """Calculate a rolling moving average requiring a full lookback window."""
    return prices.rolling(window=window, min_periods=window).mean()


def get_month_end_trading_days(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Return the last available trading day in each calendar month."""
    dates = pd.Series(index=index, data=index)
    month_ends = dates.groupby(index.to_period("M")).max()
    return pd.DatetimeIndex(month_ends.values)


def absolute_momentum_filter(
    prices: pd.DataFrame,
    momentum: pd.DataFrame,
    moving_average: pd.DataFrame,
) -> pd.DataFrame:
    """Return True where both absolute momentum filters pass."""
    return (momentum > 0.0) & (prices > moving_average)


def generate_raw_signal_weights(
    prices: pd.DataFrame,
    top_n: int = 3,
    short_lag: int = 21,
    long_lag: int = 252,
    ma_window: int = 200,
) -> pd.DataFrame:
    """Generate unscaled ETF weights on month-end signal dates.

    Passing assets are ranked by 12-1 momentum. Up to top_n assets receive
    equal weights of 1/top_n, leaving residual capital in cash when fewer than
    top_n assets pass the filters.
    """
    momentum = calculate_12_1_momentum(prices, short_lag=short_lag, long_lag=long_lag)
    moving_average = calculate_moving_average(prices, window=ma_window)
    passed = absolute_momentum_filter(prices, momentum, moving_average)
    signal_dates = get_month_end_trading_days(prices.index)

    weights = pd.DataFrame(0.0, index=signal_dates, columns=prices.columns)
    for date in signal_dates:
        eligible_momentum = momentum.loc[date].where(passed.loc[date]).dropna()
        if eligible_momentum.empty:
            continue
        selected = eligible_momentum.sort_values(ascending=False).head(top_n).index
        weights.loc[date, selected] = 1.0 / top_n
    return weights


def generate_latest_target_weights(
    prices: pd.DataFrame,
    top_n: int = 3,
    short_lag: int = 21,
    long_lag: int = 252,
    ma_window: int = 200,
) -> pd.Series:
    """Generate the latest available target weights from existing signal logic."""
    weights = generate_raw_signal_weights(
        prices=prices,
        top_n=top_n,
        short_lag=short_lag,
        long_lag=long_lag,
        ma_window=ma_window,
    )
    if weights.empty:
        return pd.Series(0.0, index=prices.columns, name=prices.index[-1])
    latest = weights.iloc[-1].reindex(prices.columns).fillna(0.0)
    latest.name = weights.index[-1]
    return latest


def map_signal_dates_to_execution_dates(
    signal_dates: pd.DatetimeIndex,
    trading_index: pd.DatetimeIndex,
) -> pd.Series:
    """Map each signal date to the next trading day execution date."""
    positions = trading_index.searchsorted(signal_dates, side="right")
    valid = positions < len(trading_index)
    return pd.Series(
        trading_index[positions[valid]],
        index=signal_dates[valid],
        name="execution_date",
    )
