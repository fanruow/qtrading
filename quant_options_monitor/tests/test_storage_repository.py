from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

from quant_options_monitor.options.models import (
    OptionContract,
    OptionLeg,
    OptionStrategyCandidate,
)
from quant_options_monitor.storage.repository import SQLiteSignalRepository
from quant_options_monitor.strategies.equity_signal import EquitySignal


def equity_signal() -> EquitySignal:
    return EquitySignal(
        symbol="spy",
        signal_type="BUY_BIAS",
        score=88.5,
        confidence=0.82,
        reasons=["Test bullish signal."],
        timestamp=datetime(2026, 5, 26, 14, 30, tzinfo=timezone.utc),
    )


def option_candidate() -> OptionStrategyCandidate:
    option = OptionContract(
        symbol="SPY260619C00500000",
        underlying_symbol="SPY",
        expiration=datetime.now(timezone.utc).date() + timedelta(days=30),
        strike=500.0,
        option_type="call",
        bid=4.0,
        ask=4.4,
        last=4.2,
        volume=1000,
        open_interest=5000,
        implied_volatility=0.25,
        delta=0.5,
    )
    return OptionStrategyCandidate(
        strategy_name="bull_call_spread",
        underlying_symbol="SPY",
        legs=[OptionLeg(action="buy", option=option, quantity=1)],
        max_loss=440.0,
        max_profit=560.0,
        breakevens=[504.4],
        estimated_debit_or_credit=-440.0,
        score=91.2,
        reasons=["Test option candidate."],
        warnings=["Alert only."],
    )


def test_save_equity_signal_to_temp_sqlite_database(tmp_path) -> None:
    db_path = tmp_path / "signals.sqlite"
    repo = SQLiteSignalRepository(db_path)

    row_id = repo.save_equity_signal(equity_signal(), regime="BULLISH_TREND")

    assert row_id == 1
    with sqlite3.connect(db_path) as connection:
        row = connection.execute(
            "SELECT symbol, signal_type, regime, score, payload_json FROM signals"
        ).fetchone()
    assert row[0] == "SPY"
    assert row[1] == "BUY_BIAS"
    assert row[2] == "BULLISH_TREND"
    assert row[3] == 88.5
    assert '"symbol": "SPY"' in row[4]
    assert '"timestamp": "2026-05-26T14:30:00Z"' in row[4]


def test_save_option_candidate_to_temp_sqlite_database(tmp_path) -> None:
    db_path = tmp_path / "signals.sqlite"
    repo = SQLiteSignalRepository(db_path)

    row_id = repo.save_option_candidate(option_candidate())

    assert row_id == 1
    with sqlite3.connect(db_path) as connection:
        row = connection.execute(
            "SELECT symbol, strategy_name, score, payload_json FROM option_candidates"
        ).fetchone()
    assert row[0] == "SPY"
    assert row[1] == "bull_call_spread"
    assert row[2] == 91.2
    assert '"strategy_name": "bull_call_spread"' in row[3]
    assert '"mid_price": 4.2' in row[3]


def test_get_recent_signals_returns_decoded_payloads_and_symbol_filter(tmp_path) -> None:
    db_path = tmp_path / "signals.sqlite"
    repo = SQLiteSignalRepository(db_path)
    repo.save_equity_signal(equity_signal(), regime="BULLISH_TREND")
    repo.save_option_candidate(option_candidate())

    all_records = repo.get_recent_signals(limit=10)
    spy_records = repo.get_recent_signals(symbol="spy", limit=10)
    missing_records = repo.get_recent_signals(symbol="QQQ", limit=10)

    assert len(all_records) == 2
    assert len(spy_records) == 2
    assert missing_records == []
    assert {record.record_type for record in all_records} == {
        "equity_signal",
        "option_candidate",
    }
    assert all(record.symbol == "SPY" for record in spy_records)
    assert all(isinstance(record.payload, dict) for record in spy_records)


def test_get_recent_signals_respects_limit(tmp_path) -> None:
    repo = SQLiteSignalRepository(tmp_path / "signals.sqlite")
    repo.save_equity_signal(equity_signal(), regime="BULLISH_TREND")
    repo.save_option_candidate(option_candidate())

    records = repo.get_recent_signals(limit=1)

    assert len(records) == 1
