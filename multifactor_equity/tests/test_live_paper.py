from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from src.live.alpaca_broker import AlpacaPaperBroker
from src.live.broker_interface import BrokerAccount, BrokerInterface, BrokerPosition, LiveOrder
from src.live.paper_trader import PaperTrader


class FakeBroker(BrokerInterface):
    def __init__(self, paper: bool = True, market_open: bool = True, positions: list[BrokerPosition] | None = None):
        self.paper = paper
        self.market_open = market_open
        self.positions = positions or []
        self.submitted: list[LiveOrder] = []

    def assert_paper(self) -> None:
        if not self.paper:
            raise ValueError("not paper")

    def is_market_open(self) -> bool:
        return self.market_open

    def get_account(self) -> BrokerAccount:
        return BrokerAccount(equity=100_000.0, cash=50_000.0, buying_power=100_000.0)

    def get_positions(self) -> list[BrokerPosition]:
        return self.positions

    def submit_order(self, order: LiveOrder) -> dict:
        self.submitted.append(order)
        return {"client_order_id": order.client_order_id, "ticker": order.ticker, "side": order.side, "qty": order.qty}


def write_signals(tmp_path, target=None, decisions=None, explanations=None, signal_date="2026-05-24"):
    target = target if target is not None else pd.DataFrame(
        {
            "ticker": ["AAA", "BBB"],
            "target_weight": [0.02, 0.01],
            "sector": ["Tech", "Health"],
            "signal_date": [signal_date, signal_date],
            "execution_date": [signal_date, signal_date],
        }
    )
    decisions = decisions if decisions is not None else pd.DataFrame(
        {
            "ticker": ["AAA", "BBB"],
            "decision": ["BUY", "ADD"],
            "sector": ["Tech", "Health"],
            "explanation": ["AAA factor explanation", "BBB factor explanation"],
        }
    )
    explanations = explanations if explanations is not None else decisions[["ticker", "explanation"]]
    target_path = tmp_path / "latest_target_portfolio.csv"
    decisions_path = tmp_path / "latest_decisions.csv"
    explanations_path = tmp_path / "decision_explanations.csv"
    target.to_csv(target_path, index=False)
    decisions.to_csv(decisions_path, index=False)
    explanations.to_csv(explanations_path, index=False)
    return target_path, decisions_path, explanations_path


def live_config(tmp_path, **overrides):
    target_path, decisions_path, explanations_path = write_signals(tmp_path, **overrides.pop("signals", {}))
    cfg = {
        "paper_trading": {
            "enabled": True,
            "broker": "alpaca",
            "paper": True,
            "signal_source": {
                "target_portfolio_path": str(target_path),
                "decisions_path": str(decisions_path),
                "explanations_path": str(explanations_path),
            },
            "execution": {
                "dry_run_default": True,
                "order_type": "market",
                "time_in_force": "day",
                "allow_fractional_shares": False,
                "min_trade_notional": 100,
                "min_weight_change": 0.0025,
                "sell_before_buy": True,
            },
            "risk": {
                "long_only": True,
                "max_single_name_weight": 0.025,
                "max_sector_weight": 0.25,
                "max_gross_exposure": 1.0,
                "cash_buffer_pct": 0.02,
                "max_orders_per_run": 100,
                "max_turnover_per_run": 0.50,
                "block_short_sales": True,
                "reject_if_market_closed": True,
                "reject_if_stale_signal": True,
                "max_signal_age_days": 3,
            },
        }
    }
    for section, values in overrides.items():
        cfg["paper_trading"][section].update(values)
    return cfg


def test_dry_run_does_not_submit_orders(tmp_path):
    broker = FakeBroker()
    result = PaperTrader(live_config(tmp_path), broker=broker, output_dir=tmp_path).run(dry_run=True, execute=False, today=date(2026, 5, 25))

    assert len(result["orders_preview"]) == 2
    assert broker.submitted == []
    assert (tmp_path / "orders_preview.csv").exists()


def test_execute_submits_orders_only_when_execute_true(tmp_path):
    broker = FakeBroker()
    result = PaperTrader(live_config(tmp_path), broker=broker, output_dir=tmp_path).run(dry_run=False, execute=True, today=date(2026, 5, 25))

    assert len(broker.submitted) == 2
    assert len(result["submitted_orders"]) == 2


def test_missing_api_key_errors(monkeypatch):
    monkeypatch.delenv("ALPACA_API_KEY", raising=False)
    monkeypatch.delenv("ALPACA_SECRET_KEY", raising=False)

    with pytest.raises(ValueError, match="ALPACA_API_KEY"):
        AlpacaPaperBroker()


def test_non_paper_environment_rejects_orders(tmp_path):
    broker = FakeBroker(paper=False)

    with pytest.raises(ValueError, match="not paper"):
        PaperTrader(live_config(tmp_path), broker=broker, output_dir=tmp_path).run(dry_run=False, execute=True, today=date(2026, 5, 25))


def test_sell_before_buy_ordering(tmp_path):
    target = pd.DataFrame(
        {
            "ticker": ["BUYME"],
            "target_weight": [0.02],
            "sector": ["Tech"],
            "signal_date": ["2026-05-24"],
            "execution_date": ["2026-05-24"],
        }
    )
    decisions = pd.DataFrame({"ticker": ["BUYME", "SELLME"], "decision": ["BUY", "SELL"], "sector": ["Tech", "Energy"], "explanation": ["buy", "sell"]})
    cfg = live_config(tmp_path, signals={"target": target, "decisions": decisions}, risk={"block_short_sales": False})
    broker = FakeBroker(positions=[BrokerPosition("SELLME", 2_000.0, 10)])

    PaperTrader(cfg, broker=broker, output_dir=tmp_path).run(dry_run=False, execute=True, today=date(2026, 5, 25))

    assert [order.side for order in broker.submitted] == ["sell", "buy"]


def test_min_trade_notional_filters_order(tmp_path):
    cfg = live_config(tmp_path, execution={"min_trade_notional": 10_000})
    result = PaperTrader(cfg, broker=FakeBroker(), output_dir=tmp_path).run(dry_run=True, execute=False, today=date(2026, 5, 25))

    assert result["orders_preview"].empty
    assert set(result["rejected_orders"]["reject_reason"]) == {"below_min_trade_notional"}


def test_min_weight_change_filters_order(tmp_path):
    target = pd.DataFrame({"ticker": ["AAA"], "target_weight": [0.001], "sector": ["Tech"], "signal_date": ["2026-05-24"], "execution_date": ["2026-05-24"]})
    cfg = live_config(tmp_path, signals={"target": target})
    result = PaperTrader(cfg, broker=FakeBroker(), output_dir=tmp_path).run(dry_run=True, execute=False, today=date(2026, 5, 25))

    assert result["orders_preview"].empty
    assert result["rejected_orders"]["reject_reason"].iloc[0] == "below_min_weight_change"


def test_long_only_rejects_negative_target(tmp_path):
    target = pd.DataFrame({"ticker": ["AAA"], "target_weight": [-0.01], "sector": ["Tech"], "signal_date": ["2026-05-24"], "execution_date": ["2026-05-24"]})
    cfg = live_config(tmp_path, signals={"target": target})

    with pytest.raises(ValueError, match="long-only"):
        PaperTrader(cfg, broker=FakeBroker(), output_dir=tmp_path).run(dry_run=True, execute=False, today=date(2026, 5, 25))


def test_max_single_name_weight_rejects(tmp_path):
    target = pd.DataFrame({"ticker": ["AAA"], "target_weight": [0.05], "sector": ["Tech"], "signal_date": ["2026-05-24"], "execution_date": ["2026-05-24"]})
    cfg = live_config(tmp_path, signals={"target": target})

    with pytest.raises(ValueError, match="max_single_name_weight"):
        PaperTrader(cfg, broker=FakeBroker(), output_dir=tmp_path).run(dry_run=True, execute=False, today=date(2026, 5, 25))


def test_max_turnover_per_run_rejects(tmp_path):
    target = pd.DataFrame({"ticker": ["AAA", "BBB"], "target_weight": [0.025, 0.025], "sector": ["Tech", "Health"], "signal_date": ["2026-05-24"] * 2, "execution_date": ["2026-05-24"] * 2})
    cfg = live_config(tmp_path, signals={"target": target}, risk={"max_turnover_per_run": 0.01})

    with pytest.raises(ValueError, match="max_turnover_per_run"):
        PaperTrader(cfg, broker=FakeBroker(), output_dir=tmp_path).run(dry_run=True, execute=False, today=date(2026, 5, 25))


def test_stale_signal_rejected(tmp_path):
    cfg = live_config(tmp_path, signals={"signal_date": "2026-05-01"})

    with pytest.raises(ValueError, match="stale signal"):
        PaperTrader(cfg, broker=FakeBroker(), output_dir=tmp_path).run(dry_run=True, execute=False, today=date(2026, 5, 25))


def test_submitted_order_records_factor_explanation(tmp_path):
    broker = FakeBroker()
    result = PaperTrader(live_config(tmp_path), broker=broker, output_dir=tmp_path).run(dry_run=False, execute=True, today=date(2026, 5, 25))

    assert "factor_explanation" in result["submitted_orders"].columns
    assert result["submitted_orders"]["factor_explanation"].str.contains("factor explanation").all()
