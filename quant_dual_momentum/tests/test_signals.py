import numpy as np
import pandas as pd

from src.signals import (
    absolute_momentum_filter,
    calculate_12_1_momentum,
    calculate_moving_average,
    generate_raw_signal_weights,
    get_month_end_trading_days,
    map_signal_dates_to_execution_dates,
)


def test_12_1_momentum_calculation_is_correct():
    dates = pd.bdate_range("2020-01-01", periods=260)
    prices = pd.DataFrame({"SPY": np.arange(1, 261, dtype=float)}, index=dates)

    momentum = calculate_12_1_momentum(prices, short_lag=21, long_lag=252)

    expected = prices["SPY"].iloc[-22] / prices["SPY"].iloc[-253] - 1.0
    assert momentum["SPY"].iloc[-1] == expected


def test_200_day_moving_average_filter_is_correct():
    dates = pd.bdate_range("2020-01-01", periods=205)
    prices = pd.DataFrame(
        {
            "PASS": np.r_[np.full(200, 100.0), np.full(5, 120.0)],
            "FAIL": np.r_[np.full(200, 100.0), np.full(5, 80.0)],
        },
        index=dates,
    )
    momentum = pd.DataFrame(0.10, index=dates, columns=prices.columns)
    ma = calculate_moving_average(prices, window=200)

    passed = absolute_momentum_filter(prices, momentum, ma)

    assert bool(passed["PASS"].iloc[-1])
    assert not bool(passed["FAIL"].iloc[-1])


def test_month_end_trading_day_identification_is_correct():
    dates = pd.DatetimeIndex(
        ["2023-01-30", "2023-01-31", "2023-02-27", "2023-02-28", "2023-03-30"]
    )

    month_ends = get_month_end_trading_days(dates)

    assert list(month_ends) == [
        pd.Timestamp("2023-01-31"),
        pd.Timestamp("2023-02-28"),
        pd.Timestamp("2023-03-30"),
    ]


def test_no_assets_passing_filter_produces_zero_weights_and_cash_one():
    dates = pd.bdate_range("2020-01-01", periods=80)
    prices = pd.DataFrame({"SPY": 100.0, "QQQ": 100.0}, index=dates)

    weights = generate_raw_signal_weights(
        prices,
        top_n=3,
        short_lag=2,
        long_lag=20,
        ma_window=10,
    )

    assert (weights.sum(axis=1) == 0.0).all()
    assert ((1.0 - weights.sum(axis=1)) == 1.0).all()


def test_signal_maps_to_next_trading_day_to_avoid_lookahead():
    dates = pd.bdate_range("2023-01-27", periods=5)
    signal_dates = pd.DatetimeIndex([pd.Timestamp("2023-01-31")])

    mapping = map_signal_dates_to_execution_dates(signal_dates, dates)

    assert mapping.loc[pd.Timestamp("2023-01-31")] == pd.Timestamp("2023-02-01")
