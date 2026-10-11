"""Alert-only scan command for equities and options candidates."""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd

from quant_options_monitor.alerts.base import AlertMessage, BaseAlertSender
from quant_options_monitor.alerts.console import ConsoleAlertSender
from quant_options_monitor.alerts.email import EmailAlertSender, EmailAlertSettings
from quant_options_monitor.alerts.formatters import format_options_candidate_alert
from quant_options_monitor.alerts.telegram import TelegramAlertSender, TelegramAlertSettings
from quant_options_monitor.data.base import BaseMarketDataProvider, MarketDataError
from quant_options_monitor.features.pipeline import build_technical_features
from quant_options_monitor.features.regime import MarketRegimeClassifier, RegimeResult
from quant_options_monitor.options.mock_provider import MockOptionsProvider
from quant_options_monitor.options.models import OptionStrategyCandidate
from quant_options_monitor.options.provider_base import BaseOptionsProvider
from quant_options_monitor.options.selector import (
    OptionsStrategySelector,
    OptionsStrategySelectorSettings,
)
from quant_options_monitor.risk.trade_filters import validate_strategy_liquidity
from quant_options_monitor.storage.repository import SQLiteSignalRepository
from quant_options_monitor.strategies.equity_signal import EquitySignal, EquitySignalEngine


@dataclass(frozen=True)
class ScanSettings(OptionsStrategySelectorSettings):
    market_data_provider: str = "mock"
    options_provider: str = "mock"
    period: str = "1y"
    interval: str = "1d"
    top_candidates: int = 3
    min_score: float = 0.65
    alert: str = "console"
    use_mock_options: bool = True
    database_path: str = "quant_options_monitor.sqlite"


@dataclass(frozen=True)
class ScanResult:
    symbol: str
    latest_price: float | None
    regime: RegimeResult | None
    equity_signal: EquitySignal | None
    candidates: list[OptionStrategyCandidate] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    error: str | None = None


class MockMarketDataProvider(BaseMarketDataProvider):
    """Deterministic OHLCV provider for local scans and tests."""

    def get_price_history(self, symbol: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
        if symbol.upper().startswith("FAIL"):
            raise MarketDataError(f"Mock failure requested for {symbol}")

        rows = 260
        index = pd.date_range(end=datetime.now(timezone.utc).date(), periods=rows, freq="B")
        base = pd.Series(np.arange(rows, dtype=float), index=index)
        seed = sum(ord(char) for char in symbol.upper())
        anchor = 80.0 + seed % 240
        drift = ((seed % 7) - 3) * 0.015
        cycle = np.sin(base / 4.0) * (1.0 + (seed % 5) * 0.15)
        close = anchor + base * drift + cycle
        volume = 1_000_000 + (base % 20) * 30_000 + (seed % 11) * 5_000
        return pd.DataFrame(
            {
                "open": close - 0.15,
                "high": close + 1.25,
                "low": close - 1.25,
                "close": close,
                "volume": volume,
            },
            index=index,
        )

    def get_latest_price(self, symbol: str) -> float:
        history = self.get_price_history(symbol, period="5d", interval="1d")
        close = history["close"].dropna()
        if close.empty:
            raise MarketDataError(f"No latest close price available for {symbol}")
        return float(close.iloc[-1])


def load_settings() -> ScanSettings:
    """Load scan settings. Placeholder for config/env support."""

    return ScanSettings()


def load_market_data_provider(settings: ScanSettings) -> BaseMarketDataProvider:
    """Load the configured market data provider."""

    if settings.market_data_provider == "mock":
        return MockMarketDataProvider()
    raise ValueError(f"Unsupported market data provider: {settings.market_data_provider}")


def load_options_provider(
    settings: ScanSettings, underlying_prices: dict[str, float] | None = None
) -> BaseOptionsProvider:
    """Load the configured options provider."""

    if settings.options_provider == "mock" and settings.use_mock_options:
        return MockOptionsProvider(underlying_prices=underlying_prices)
    raise ValueError(f"Unsupported options provider: {settings.options_provider}")


def scan_symbol(
    symbol: str,
    *,
    market_data_provider: BaseMarketDataProvider,
    settings: ScanSettings,
    options_provider: BaseOptionsProvider | None = None,
) -> ScanResult:
    """Run the full scan pipeline for one symbol."""

    normalized_symbol = symbol.strip().upper()
    price_history = market_data_provider.get_price_history(
        normalized_symbol,
        period=settings.period,
        interval=settings.interval,
    )
    latest_price = float(price_history["close"].dropna().iloc[-1])
    features = build_technical_features(price_history)
    regime = MarketRegimeClassifier().classify(normalized_symbol, features)
    equity_signal = EquitySignalEngine().generate(normalized_symbol, features)

    provider = options_provider or load_options_provider(
        settings,
        underlying_prices={normalized_symbol: latest_price},
    )
    option_chain = provider.get_chain(normalized_symbol)
    selector = OptionsStrategySelector()
    candidates = selector.select(
        normalized_symbol,
        option_chain,
        regime,
        settings,
    )[: settings.top_candidates]

    warnings = [
        warning
        for candidate in candidates
        for warning in candidate.warnings
    ]
    reasons = [*regime.reasons, *equity_signal.reasons]
    return ScanResult(
        symbol=normalized_symbol,
        latest_price=latest_price,
        regime=regime,
        equity_signal=equity_signal,
        candidates=candidates,
        reasons=reasons,
        warnings=warnings,
    )


def process_scan_result(
    result: ScanResult,
    *,
    repository: SQLiteSignalRepository,
    alert_senders: Sequence[BaseAlertSender],
    settings: ScanSettings,
) -> int:
    """Persist scan output and send alerts for qualified candidates."""

    if result.error:
        return 0

    if result.equity_signal is not None:
        repository.save_equity_signal(
            result.equity_signal,
            regime=str(result.regime.regime) if result.regime else None,
        )

    alerts_sent = 0
    for candidate in result.candidates[: settings.top_candidates]:
        repository.save_option_candidate(candidate)
        if not should_alert_candidate(candidate, settings):
            continue
        if result.latest_price is None or result.regime is None:
            continue
        body = format_options_candidate_alert(
            symbol=result.symbol,
            latest_price=result.latest_price,
            regime_result=result.regime,
            candidate=candidate,
        )
        alert = AlertMessage(
            title=f"{_title_case(candidate.strategy_name)} Candidate",
            symbol=result.symbol,
            severity="INFO",
            body=body,
            metadata={"score": candidate.score, "strategy": candidate.strategy_name},
        )
        for sender in alert_senders:
            sender.send_alert(alert)
        alerts_sent += 1
    return alerts_sent


def should_alert_candidate(candidate: OptionStrategyCandidate, settings: ScanSettings) -> bool:
    """Return whether a candidate qualifies for outbound alerting."""

    threshold = _score_threshold(settings.min_score)
    if candidate.score < threshold:
        return False
    is_liquid, _warnings = validate_strategy_liquidity(candidate, settings)
    if not is_liquid:
        return False
    return not has_critical_warnings(candidate)


def has_critical_warnings(candidate: OptionStrategyCandidate) -> bool:
    """Treat rejection and naked-risk warnings as critical alert blockers."""

    critical_markers = ("critical", "rejected", "naked")
    return any(
        any(marker in warning.lower() for marker in critical_markers)
        for warning in candidate.warnings
    )


def load_alert_senders(alert: str) -> list[BaseAlertSender]:
    """Load alert senders from CLI selection and environment settings."""

    if alert == "none":
        return []
    if alert == "console":
        return [ConsoleAlertSender()]
    if alert == "email":
        return [
            EmailAlertSender(
                EmailAlertSettings(
                    smtp_host=os.getenv("QOM_EMAIL_SMTP_HOST"),
                    smtp_port=int(os.getenv("QOM_EMAIL_SMTP_PORT", "587")),
                    username=os.getenv("QOM_EMAIL_USERNAME"),
                    password=os.getenv("QOM_EMAIL_PASSWORD"),
                    from_address=os.getenv("QOM_EMAIL_FROM"),
                    to_addresses=[
                        item.strip()
                        for item in os.getenv("QOM_EMAIL_TO", "").split(",")
                        if item.strip()
                    ],
                )
            )
        ]
    if alert == "telegram":
        return [
            TelegramAlertSender(
                TelegramAlertSettings(
                    bot_token=os.getenv("QOM_TELEGRAM_BOT_TOKEN"),
                    chat_id=os.getenv("QOM_TELEGRAM_CHAT_ID"),
                )
            )
        ]
    raise ValueError(f"Unsupported alert channel: {alert}")


def _score_threshold(min_score: float) -> float:
    return min_score * 100 if 0 <= min_score <= 1 else min_score


def _title_case(value: str) -> str:
    return value.replace("_", " ").title()


def scan_symbols(
    symbols: Sequence[str],
    *,
    settings: ScanSettings | None = None,
    market_data_provider: BaseMarketDataProvider | None = None,
) -> list[ScanResult]:
    """Scan multiple symbols with per-symbol error isolation."""

    settings = settings or load_settings()
    market_data_provider = market_data_provider or load_market_data_provider(settings)
    results: list[ScanResult] = []
    for symbol in symbols:
        normalized_symbol = symbol.strip().upper()
        try:
            results.append(
                scan_symbol(
                    normalized_symbol,
                    market_data_provider=market_data_provider,
                    settings=settings,
                )
            )
        except Exception as exc:
            results.append(
                ScanResult(
                    symbol=normalized_symbol,
                    latest_price=None,
                    regime=None,
                    equity_signal=None,
                    candidates=[],
                    reasons=[],
                    warnings=["Symbol scan failed; continuing with remaining symbols."],
                    error=str(exc),
                )
            )
    return results


def format_scan_result(result: ScanResult) -> str:
    """Format a scan result as structured console text."""

    lines = [f"Symbol: {result.symbol}"]
    if result.error:
        lines.extend(
            [
                "Status: ERROR",
                f"Error: {result.error}",
                "Warnings:",
                *[f"  - {warning}" for warning in result.warnings],
            ]
        )
        return "\n".join(lines)

    lines.extend(
        [
            "Status: OK",
            f"Latest Price: {result.latest_price:.2f}" if result.latest_price is not None else "Latest Price: n/a",
            f"Regime: {result.regime.regime}" if result.regime else "Regime: n/a",
            (
                f"Equity Bias: {result.equity_signal.signal_type} "
                f"(score={result.equity_signal.score:.2f}, "
                f"confidence={result.equity_signal.confidence:.2f})"
                if result.equity_signal
                else "Equity Bias: n/a"
            ),
            "Reasons:",
        ]
    )
    lines.extend(f"  - {reason}" for reason in result.reasons)
    lines.append("Top Options Candidates:")
    if result.candidates:
        for index, candidate in enumerate(result.candidates, start=1):
            lines.extend(
                [
                    f"  {index}. {candidate.strategy_name} score={candidate.score:.2f}",
                    f"     max_loss={candidate.max_loss} max_profit={candidate.max_profit}",
                    f"     breakevens={candidate.breakevens}",
                    f"     estimated_debit_or_credit={candidate.estimated_debit_or_credit}",
                ]
            )
            for reason in candidate.reasons:
                lines.append(f"     reason: {reason}")
            for warning in candidate.warnings:
                lines.append(f"     warning: {warning}")
    else:
        lines.append("  - none")
    if result.warnings:
        lines.append("Warnings:")
        lines.extend(f"  - {warning}" for warning in sorted(set(result.warnings)))
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Quant options monitor scan command")
    parser.add_argument("--symbols", nargs="+", required=True)
    parser.add_argument("--mode", choices=["scan"], default="scan")
    parser.add_argument("--alert", choices=["console", "email", "telegram", "none"], default="console")
    parser.add_argument("--top-n", type=int, default=3)
    parser.add_argument("--min-score", type=float, default=0.65)
    parser.add_argument("--use-mock-options", choices=["true", "false"], default="true")
    parser.add_argument("--db-path", default="quant_options_monitor.sqlite")
    args = parser.parse_args(argv)

    settings = ScanSettings(
        top_candidates=args.top_n,
        min_score=args.min_score,
        alert=args.alert,
        use_mock_options=args.use_mock_options.lower() == "true",
        database_path=args.db_path,
    )
    repository = SQLiteSignalRepository(Path(settings.database_path))
    alert_senders = load_alert_senders(settings.alert)
    if args.mode == "scan":
        for result in scan_symbols(args.symbols, settings=settings):
            print(format_scan_result(result))
            process_scan_result(
                result,
                repository=repository,
                alert_senders=alert_senders,
                settings=settings,
            )
            print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
