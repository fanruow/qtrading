from __future__ import annotations

import pandas as pd
import pytest

from quant_options_monitor.alerts.base import AlertMessage, BaseAlertSender
from quant_options_monitor.app.scheduler import (
    MockMarketDataProvider,
    ScanResult,
    ScanSettings,
    format_scan_result,
    main,
    process_scan_result,
    scan_symbol,
    scan_symbols,
    should_alert_candidate,
)
from quant_options_monitor.data.base import BaseMarketDataProvider, MarketDataError
from quant_options_monitor.features.regime import MarketRegime, RegimeResult
from quant_options_monitor.options.mock_provider import MockOptionsProvider
from quant_options_monitor.options.models import OptionStrategyCandidate
from quant_options_monitor.options.strategies.call_spread import BullCallSpreadSelector
from quant_options_monitor.storage.repository import SQLiteSignalRepository


def test_scan_symbol_with_mock_data_returns_structured_result() -> None:
    result = scan_symbol(
        "SPY",
        market_data_provider=MockMarketDataProvider(),
        settings=ScanSettings(),
    )

    assert result.symbol == "SPY"
    assert result.latest_price is not None
    assert result.regime is not None
    assert result.equity_signal is not None
    assert isinstance(result.candidates, list)
    assert result.error is None


def test_format_scan_result_includes_required_sections() -> None:
    result = scan_symbol(
        "QQQ",
        market_data_provider=MockMarketDataProvider(),
        settings=ScanSettings(),
    )

    output = format_scan_result(result)

    assert "Symbol: QQQ" in output
    assert "Latest Price:" in output
    assert "Regime:" in output
    assert "Equity Bias:" in output
    assert "Top Options Candidates:" in output
    assert "Reasons:" in output


def test_scan_symbols_isolates_failing_symbol() -> None:
    results = scan_symbols(
        ["SPY", "FAILME", "QQQ"],
        settings=ScanSettings(),
        market_data_provider=MockMarketDataProvider(),
    )

    assert [result.symbol for result in results] == ["SPY", "FAILME", "QQQ"]
    assert results[0].error is None
    assert results[1].error is not None
    assert results[2].error is None
    assert "continuing" in " ".join(results[1].warnings)


def test_main_scan_prints_console_output(capsys: pytest.CaptureFixture[str], tmp_path) -> None:
    exit_code = main(
        [
            "--symbols",
            "SPY",
            "QQQ",
            "--mode",
            "scan",
            "--alert",
            "none",
            "--db-path",
            str(tmp_path / "scan.sqlite"),
        ]
    )

    captured = capsys.readouterr().out
    assert exit_code == 0
    assert "Symbol: SPY" in captured
    assert "Symbol: QQQ" in captured
    assert "Top Options Candidates:" in captured


class EmptyMarketDataProvider(BaseMarketDataProvider):
    def get_price_history(self, symbol: str, period: str, interval: str) -> pd.DataFrame:
        raise MarketDataError("empty test provider")

    def get_latest_price(self, symbol: str) -> float:
        raise MarketDataError("empty test provider")


def test_scan_symbols_handles_provider_errors() -> None:
    results = scan_symbols(
        ["SPY"],
        settings=ScanSettings(),
        market_data_provider=EmptyMarketDataProvider(),
    )

    assert results[0].symbol == "SPY"
    assert results[0].error == "empty test provider"


class FakeAlertSender(BaseAlertSender):
    def __init__(self) -> None:
        self.alerts: list[AlertMessage] = []

    def send_alert(self, alert: AlertMessage) -> None:
        self.alerts.append(alert)


def high_score_candidate() -> OptionStrategyCandidate:
    option_chain = MockOptionsProvider(
        underlying_prices={"SPY": 500.0},
    ).get_chain("SPY")
    regime = RegimeResult(
        symbol="SPY",
        regime=MarketRegime.BULLISH_TREND,
        trend_score=0.95,
        range_score=0.0,
        volatility_score=0.0,
        reasons=["Bullish test regime."],
    )
    candidate = BullCallSpreadSelector().select(
        "SPY",
        option_chain.underlying_price,
        option_chain,
        regime,
        ScanSettings(),
    )
    assert candidate is not None
    candidate.score = 95.0
    return candidate


def test_process_scan_result_saves_records_and_sends_console_eligible_alert(tmp_path) -> None:
    settings = ScanSettings(top_candidates=3, min_score=0.65)
    repository = SQLiteSignalRepository(tmp_path / "scan.sqlite")
    sender = FakeAlertSender()
    base_result = scan_symbol(
        "SPY",
        market_data_provider=MockMarketDataProvider(),
        settings=settings,
    )
    result = ScanResult(
        symbol=base_result.symbol,
        latest_price=500.0,
        regime=RegimeResult(
            symbol="SPY",
            regime=MarketRegime.BULLISH_TREND,
            trend_score=0.95,
            range_score=0.0,
            volatility_score=0.0,
            reasons=["Bullish test regime."],
        ),
        equity_signal=base_result.equity_signal,
        candidates=[high_score_candidate()],
        reasons=base_result.reasons,
        warnings=[],
    )

    alerts_sent = process_scan_result(
        result,
        repository=repository,
        alert_senders=[sender],
        settings=settings,
    )
    records = repository.get_recent_signals(symbol="SPY", limit=10)

    assert alerts_sent == 1
    assert len(sender.alerts) == 1
    assert "[OPTIONS SIGNAL] SPY" in sender.alerts[0].body
    assert {record.record_type for record in records} == {"equity_signal", "option_candidate"}


def test_process_scan_result_does_not_alert_low_score_candidate(tmp_path) -> None:
    settings = ScanSettings(top_candidates=3, min_score=0.90)
    repository = SQLiteSignalRepository(tmp_path / "scan.sqlite")
    sender = FakeAlertSender()
    candidate = high_score_candidate()
    candidate.score = 50.0
    result = ScanResult(
        symbol="SPY",
        latest_price=500.0,
        regime=RegimeResult(
            symbol="SPY",
            regime=MarketRegime.BULLISH_TREND,
            trend_score=0.95,
            range_score=0.0,
            volatility_score=0.0,
            reasons=["Bullish test regime."],
        ),
        equity_signal=scan_symbol(
            "SPY",
            market_data_provider=MockMarketDataProvider(),
            settings=settings,
        ).equity_signal,
        candidates=[candidate],
    )

    alerts_sent = process_scan_result(
        result,
        repository=repository,
        alert_senders=[sender],
        settings=settings,
    )

    assert alerts_sent == 0
    assert sender.alerts == []
    assert len(repository.get_recent_signals(symbol="SPY", limit=10)) == 2


def test_should_alert_candidate_blocks_critical_warnings() -> None:
    candidate = high_score_candidate()
    candidate.warnings.append("Rejected: naked short option risk.")

    assert not should_alert_candidate(candidate, ScanSettings(min_score=0.65))
