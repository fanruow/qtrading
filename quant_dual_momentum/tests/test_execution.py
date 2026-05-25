import pandas as pd
import pytest

from src.execution.alpaca_broker import AlpacaBroker
from src.execution.broker_base import AccountSnapshot, PlannedOrder, Position
from src.execution.order_manager import (
    generate_order_diff,
    submit_or_print_orders,
    target_weights_to_shares,
)
from src.risk.limits import LiveConfig
from src.risk.pre_trade_checks import run_pre_trade_checks


def make_config(**overrides):
    payload = {
        "symbols": ["SPY", "QQQ"],
        "max_position_weight": 0.6,
        "max_order_notional": 10_000,
        "max_total_gross_exposure": 1.0,
        "max_daily_turnover": 1.0,
        "dry_run": True,
        "paper": True,
    }
    payload.update(overrides)
    return LiveConfig(**payload)


def test_target_weights_to_target_shares_is_correct():
    weights = pd.Series({"SPY": 0.50, "QQQ": 0.25})
    prices = pd.Series({"SPY": 100.0, "QQQ": 50.0})

    shares = target_weights_to_shares(weights, equity=10_000, latest_prices=prices)

    assert shares == {"SPY": 50, "QQQ": 50}


def test_current_shares_and_target_shares_to_orders_is_correct():
    prices = pd.Series({"SPY": 100.0, "QQQ": 50.0})
    current = {"SPY": 10, "QQQ": 20}
    target = {"SPY": 15, "QQQ": 5}

    orders = generate_order_diff(current, target, prices)

    assert orders == [
        PlannedOrder("QQQ", "sell", 15, 50.0, 750.0),
        PlannedOrder("SPY", "buy", 5, 100.0, 500.0),
    ]


def test_small_orders_below_minimum_notional_are_filtered():
    prices = pd.Series({"SPY": 10.0})

    orders = generate_order_diff({"SPY": 0}, {"SPY": 1}, prices, min_order_notional=25.0)

    assert orders == []


def test_risk_blocks_oversized_order():
    config = make_config(max_order_notional=100.0)
    orders = [PlannedOrder("SPY", "buy", 2, 100.0, 200.0)]

    result = run_pre_trade_checks(
        config,
        AccountSnapshot(equity=10_000, cash=10_000),
        {"SPY": Position("SPY", 0)},
        pd.Series({"SPY": 0.5, "QQQ": 0.0}),
        orders,
        latest_data_date=pd.Timestamp.today(),
    )

    assert not result.passed
    assert any("max_order_notional" in error for error in result.errors)


def test_risk_blocks_position_above_max_weight():
    config = make_config(max_position_weight=0.4)

    result = run_pre_trade_checks(
        config,
        AccountSnapshot(equity=10_000, cash=10_000),
        {"SPY": Position("SPY", 0)},
        pd.Series({"SPY": 0.5, "QQQ": 0.0}),
        [],
        latest_data_date=pd.Timestamp.today(),
    )

    assert not result.passed
    assert any("max_position_weight" in error for error in result.errors)


def test_dry_run_does_not_call_submit_order():
    class FakeBroker:
        def __init__(self):
            self.calls = 0

        def submit_order(self, order):
            self.calls += 1

    broker = FakeBroker()
    orders = [PlannedOrder("SPY", "buy", 1, 100.0, 100.0)]

    submitted = submit_or_print_orders(broker, orders, dry_run=True)

    assert submitted == []
    assert broker.calls == 0


def test_paper_false_raises_to_prevent_live_trading():
    with pytest.raises(ValueError, match="Live trading is disabled"):
        AlpacaBroker(api_key="key", secret_key="secret", paper=False)


def test_missing_api_key_has_clear_error(monkeypatch):
    monkeypatch.delenv("ALPACA_API_KEY", raising=False)
    monkeypatch.delenv("ALPACA_SECRET_KEY", raising=False)

    with pytest.raises(ValueError, match="Missing Alpaca credentials"):
        AlpacaBroker(paper=True)


def test_stale_data_blocks_trading():
    config = make_config()

    result = run_pre_trade_checks(
        config,
        AccountSnapshot(equity=10_000, cash=10_000),
        {"SPY": Position("SPY", 0)},
        pd.Series({"SPY": 0.5, "QQQ": 0.0}),
        [],
        latest_data_date=pd.Timestamp("2020-01-01"),
        today=pd.Timestamp("2026-05-25"),
    )

    assert not result.passed
    assert any("stale" in error for error in result.errors)
