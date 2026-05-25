from __future__ import annotations

import pandas as pd
import pytest

from src.paper_trading.alpaca import AlpacaPaperBroker
from src.paper_trading.broker import Account, BrokerInterface, OrderRequest
from src.paper_trading.risk import validate_paper_targets
from src.paper_trading.runner import PaperTradingRunner
from src.utils.env import load_dotenv


class FakeBroker(BrokerInterface):
    def __init__(self, known_symbols: set[str] | None = None):
        self.known_symbols = known_symbols or {"AAA", "BBB", "CCC"}
        self.submitted: list[OrderRequest] = []

    def get_account(self) -> Account:
        return Account(equity=100_000.0, cash=100_000.0)

    def get_positions(self) -> list:
        return []

    def get_tradable_symbols(self) -> set[str]:
        return self.known_symbols

    def submit_order(self, order: OrderRequest) -> dict:
        self.submitted.append(order)
        return {"symbol": order.symbol, "side": order.side, "notional": order.notional}


def sample_config(tmp_path, execute=False, dry_run=True):
    return {
        "initial_capital": 100_000,
        "portfolio": {"top_n": 2, "max_stock_weight": 0.5, "max_sector_weight": 0.75},
        "paper_trading": {"dry_run": dry_run, "execute": execute, "cash_buffer": 0.05, "min_notional": 1.0},
    }


def sample_factor_scores():
    return pd.DataFrame(
        {
            "signal_date": [pd.Timestamp("2021-01-29")] * 3,
            "ticker": ["AAA", "BBB", "CCC"],
            "sector": ["Tech", "Health", "Tech"],
            "composite_score": [3.0, 2.0, 1.0],
            "momentum_score": [1.0, 0.5, 0.0],
            "value_score": [0.2, 0.1, 0.0],
            "quality_score": [0.3, 0.2, 0.0],
            "low_vol_score": [0.4, 0.3, 0.0],
            "missing_count": [0, 0, 0],
            "mom_12_1_sector_z": [2.0, 0.0, -1.0],
            "roe_sector_z": [1.0, 1.0, 0.0],
            "gross_margin_sector_z": [1.0, 1.0, 0.0],
            "fcf_yield": [0.03, 0.02, 0.01],
            "neg_beta_252_sector_z": [1.0, 1.0, 0.0],
        }
    )


def test_dry_run_writes_preview_and_does_not_submit(tmp_path):
    broker = FakeBroker()
    runner = PaperTradingRunner(sample_config(tmp_path), broker=broker, output_dir=tmp_path)

    result = runner.run_from_factor_scores(sample_factor_scores())

    assert (tmp_path / "orders_preview.csv").exists()
    assert (tmp_path / "paper_order_explanations.csv").exists()
    assert len(result["orders_preview"]) == 2
    assert set(result["orders_preview"]["ticker"]) == {"AAA", "BBB"}
    assert result["orders_preview"]["summary"].notna().all()
    assert broker.submitted == []


def test_execute_requires_dry_run_disabled(tmp_path):
    broker = FakeBroker()
    runner = PaperTradingRunner(sample_config(tmp_path, execute=True, dry_run=True), broker=broker, output_dir=tmp_path)

    with pytest.raises(ValueError, match="dry_run=false"):
        runner.run_from_factor_scores(sample_factor_scores())
    assert broker.submitted == []


def test_execute_submits_only_when_explicit_and_not_dry_run(tmp_path):
    broker = FakeBroker()
    runner = PaperTradingRunner(sample_config(tmp_path, execute=True, dry_run=False), broker=broker, output_dir=tmp_path)

    runner.run_from_factor_scores(sample_factor_scores())

    assert len(broker.submitted) == 2
    assert {order.symbol for order in broker.submitted} == {"AAA", "BBB"}


def test_risk_rejects_unknown_symbols():
    targets = pd.Series({"AAA": 0.2, "ZZZ": 0.1})
    factor_scores = pd.DataFrame({"ticker": ["AAA", "ZZZ"], "sector": ["Tech", "Tech"]})

    with pytest.raises(ValueError, match="unknown symbols"):
        validate_paper_targets(targets, factor_scores, {"AAA"}, 0.5, 0.75, 0.05)


def test_risk_rejects_leverage_after_cash_buffer():
    targets = pd.Series({"AAA": 0.96})
    factor_scores = pd.DataFrame({"ticker": ["AAA"], "sector": ["Tech"]})

    with pytest.raises(ValueError, match="cash-buffer"):
        validate_paper_targets(targets, factor_scores, {"AAA"}, 1.0, 1.0, 0.05)


def test_alpaca_paper_broker_rejects_non_paper_endpoint(monkeypatch):
    monkeypatch.setenv("ALPACA_API_KEY", "key")
    monkeypatch.setenv("ALPACA_SECRET_KEY", "secret")
    monkeypatch.setenv("ALPACA_PAPER_BASE_URL", "https://api.alpaca.markets")

    with pytest.raises(ValueError, match="paper endpoint"):
        AlpacaPaperBroker()


def test_alpaca_paper_broker_requires_env_keys(monkeypatch):
    monkeypatch.delenv("ALPACA_API_KEY", raising=False)
    monkeypatch.delenv("ALPACA_SECRET_KEY", raising=False)
    monkeypatch.setenv("ALPACA_PAPER_BASE_URL", "https://paper-api.alpaca.markets")

    with pytest.raises(ValueError, match="must be set"):
        AlpacaPaperBroker()


def test_dotenv_loads_alpaca_paper_env(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "ALPACA_API_KEY=paper_key",
                "ALPACA_SECRET_KEY=paper_secret",
                "ALPACA_PAPER_BASE_URL=https://paper-api.alpaca.markets",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.delenv("ALPACA_API_KEY", raising=False)
    monkeypatch.delenv("ALPACA_SECRET_KEY", raising=False)
    monkeypatch.delenv("ALPACA_PAPER_BASE_URL", raising=False)

    load_dotenv(env_file)
    broker = AlpacaPaperBroker()

    assert broker.api_key == "paper_key"
    assert broker.secret_key == "paper_secret"
    assert broker.base_url == "https://paper-api.alpaca.markets"
