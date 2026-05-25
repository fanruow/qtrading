from __future__ import annotations

import pandas as pd


def month_end_signal_dates(dates: pd.DatetimeIndex) -> pd.DatetimeIndex:
    dates = pd.DatetimeIndex(dates).sort_values()
    months = pd.Series(dates, index=dates).groupby(dates.to_period("M")).max()
    return pd.DatetimeIndex(months.values)


def next_trading_day(dates: pd.DatetimeIndex, signal_date: pd.Timestamp) -> pd.Timestamp | None:
    idx = dates.searchsorted(pd.Timestamp(signal_date), side="right")
    if idx >= len(dates):
        return None
    return pd.Timestamp(dates[idx])
