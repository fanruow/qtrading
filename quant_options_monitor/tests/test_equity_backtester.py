from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from quant_options_monitor.app import backtest as backtest_cli
from quant_options_monitor.backtest.equity_backtester import EquitySignalBacktester
from quant_options_monitor.backtest.metrics import calculate_metrics


def deterministic_ohlcv(rows: int = 120) -> pd.DataFrame:
    index = pd.date_range("2024-01-01", periods=rows, freq="B")
    base = pd.Series(np.arange(rows, dtype=float), index=index)
    close = 100.0 + base * 0.45 + np.sin(base / 6.0)
    volume = 1_000_000 + base * 1_000
    return pd.DataFrame(
        {
            "open": close - 0.2,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "volume": volume,
        },
        index=index,
    )


def test_calculate_metrics_on_known_series() -> None:
    returns = pd.Series([0.0, 0.10, -0.05, 0.20])
    equity = 100.0 * (1 + returns).cumprod()
    positions = pd.Series([0.0, 1.0, 1.0, 0.0])

    metrics = calculate_metrics(equity, returns, positions, periods_per_year=4)

    assert metrics["total_return"] == pytest.approx(equity.iloc[-1] / equity.iloc[0] - 1)
    assert metrics["cagr"] == pytest.approx((equity.iloc[-1] / equity.iloc[0]) ** (1 / 1.0) - 1)
    assert metrics["annualized_volatility"] == pytest.approx(returns.std(ddof=0) * np.sqrt(4))
    assert metrics["sharpe"] == pytest.approx(returns.mean() * 4 / metrics["annualized_volatility"])
    assert metrics["max_drawdown"] == pytest.approx((equity / equity.cummax() - 1).min())
    assert metrics["win_rate"] == pytest.approx(2 / 3)
    assert metrics["profit_factor"] == pytest.approx(0.30 / 0.05)
    assert metrics["number_of_trades"] == 2


def test_equity_backtester_uses_next_bar_positions_without_lookahead() -> None:
    prices = deterministic_ohlcv()

    result = EquitySignalBacktester(transaction_cost_bps=0.0).run("SPY", prices)

    pd.testing.assert_series_equal(
        result.positions,
        result.signals.shift(1).fillna(0.0).rename("signal_position"),
    )
    expected_returns = result.positions * prices["close"].pct_change().fillna(0.0)
    pd.testing.assert_series_equal(result.strategy_returns, expected_returns)


def test_equity_backtester_applies_transaction_cost_on_position_changes() -> None:
    prices = deterministic_ohlcv()
    no_cost = EquitySignalBacktester(transaction_cost_bps=0.0).run("SPY", prices)
    with_cost = EquitySignalBacktester(transaction_cost_bps=5.0).run("SPY", prices)

    assert with_cost.equity_curve.iloc[-1] <= no_cost.equity_curve.iloc[-1]
    assert with_cost.metrics["number_of_trades"] == no_cost.metrics["number_of_trades"]


def test_backtest_cli_prints_metrics(monkeypatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(backtest_cli, "load_price_history", lambda symbol, period: deterministic_ohlcv())

    exit_code = backtest_cli.main(["--symbol", "SPY", "--period", "5y"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Backtest: SPY period=5y" in output
    assert "total_return:" in output
    assert "number_of_trades:" in output
