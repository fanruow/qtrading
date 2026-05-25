from __future__ import annotations

import pandas as pd

from src.utils.calendar import month_end_signal_dates, next_trading_day


def test_signal_executes_on_next_trading_day():
    dates = pd.bdate_range("2020-01-01", "2020-03-10")
    signal = month_end_signal_dates(dates)[0]
    execution = next_trading_day(dates, signal)
    assert execution > signal
    assert execution == dates[dates.get_loc(signal) + 1]
