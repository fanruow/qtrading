from __future__ import annotations

import pandas as pd

from src.data.universe import build_eligible_universe


def test_fundamentals_available_date_prevents_future_leakage():
    dates = pd.bdate_range("2020-01-01", periods=260)
    close = pd.DataFrame({"AAA": 10.0}, index=dates)
    volume = pd.DataFrame({"AAA": 2_000_000.0}, index=dates)
    fundamentals = pd.DataFrame(
        {
            "ticker": ["AAA", "AAA"],
            "sector": ["Tech", "Tech"],
            "security_type": ["Common Stock", "Common Stock"],
            "is_adr": [False, False],
            "is_etf": [False, False],
            "is_otc": [False, False],
            "is_preferred": [False, False],
            "report_date": pd.to_datetime(["2019-12-31", "2020-12-31"]),
            "available_date": pd.to_datetime(["2020-01-15", "2021-01-15"]),
            "market_cap": [2e9, 9e9],
        }
    )
    cfg = {
        "min_price": 5,
        "min_avg_dollar_volume_20d": 10_000_000,
        "min_market_cap": 1_000_000_000,
        "min_history_days": 252,
        "allowed_security_type": "Common Stock",
    }
    u = build_eligible_universe(dates[-1], close, volume, fundamentals, cfg)
    assert u.loc["AAA", "market_cap"] == 2e9
