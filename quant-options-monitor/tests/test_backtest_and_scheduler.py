from __future__ import annotations

import pandas as pd

from src.app.scheduler import scan_symbols
from src.backtesting.equity import run_equity_signal_backtest
from src.config import AppConfig
from src.data.providers import SyntheticMarketDataProvider


def test_equity_backtest_metrics() -> None:
    prices = SyntheticMarketDataProvider().get_price_history("SPY")
    signals = pd.Series(1, index=prices.index)
    result = run_equity_signal_backtest(prices, signals)
    assert "CAGR" in result
    assert "Sharpe" in result
    assert result["equity_curve"].iloc[-1] > 0


def test_scheduler_scan_with_synthetic_provider() -> None:
    alerts = scan_symbols(["SPY"], AppConfig(), provider=SyntheticMarketDataProvider())
    assert alerts
    assert "SPY:" in alerts[0]
