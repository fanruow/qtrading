"""Command-line scan scheduler for alert-only research."""

from __future__ import annotations

import argparse
from typing import Sequence

from src.alerting.alerts import AlertRouter, ConsoleAlert, EmailAlert, TelegramAlert
from src.config import AppConfig, load_config
from src.data.providers import BaseMarketDataProvider, SyntheticMarketDataProvider, YFinanceMarketDataProvider
from src.features.technical import build_technical_features
from src.features.volatility import summarize_chain_volatility
from src.options.strategies import OptionsStrategySelector
from src.regime.classifier import classify_market_regime
from src.risk.manager import RiskManager


def build_provider(config: AppConfig) -> BaseMarketDataProvider:
    if config.provider == "yfinance":
        try:
            return YFinanceMarketDataProvider()
        except Exception:
            return SyntheticMarketDataProvider()
    return SyntheticMarketDataProvider()


def format_candidate(symbol: str, candidate: object, approved: bool, reasons: list[str]) -> str:
    return (
        f"{symbol}: {candidate.strategy}\n"
        f"Strikes: {candidate.candidate_strikes} | DTE: {candidate.dte}\n"
        f"Max loss: {candidate.max_loss} | Max profit: {candidate.max_profit}\n"
        f"Breakeven: {candidate.breakeven}\n"
        f"Liquidity: {candidate.liquidity_filters}\n"
        f"Risk approved: {approved} {'; '.join(reasons)}\n"
        f"Reason: {candidate.reason}"
    )


def scan_symbols(
    symbols: Sequence[str],
    config: AppConfig,
    provider: BaseMarketDataProvider | None = None,
) -> list[str]:
    provider = provider or build_provider(config)
    selector = OptionsStrategySelector(config.risk, config.strategy)
    risk = RiskManager(config.risk, config.initial_capital)
    alerts: list[str] = []
    for symbol in symbols:
        active_provider = provider
        try:
            prices = active_provider.get_price_history(symbol, period=f"{config.lookback_days}d")
        except Exception as exc:
            active_provider = SyntheticMarketDataProvider()
            prices = active_provider.get_price_history(symbol, period=f"{config.lookback_days}d")
            alerts.append(f"{symbol}: live data unavailable, using synthetic fallback data. Error: {exc}")
        features = build_technical_features(prices)
        regime = classify_market_regime(features)
        expirations = active_provider.get_expirations(symbol)
        expiration = next(
            (
                exp
                for exp in expirations
                if config.strategy.dte_min <= (exp - prices.index[-1].date()).days <= config.strategy.dte_max
            ),
            expirations[0],
        )
        chain = active_provider.get_option_chain(symbol, expiration)
        realized_vol = float(features["realized_vol_21"].dropna().iloc[-1])
        vol_features = summarize_chain_volatility(chain, realized_vol)
        spot = float(prices["close"].iloc[-1])
        for candidate in selector.select(symbol, spot, regime, chain, vol_features):
            decision = risk.evaluate(candidate)
            alerts.append(format_candidate(symbol, candidate, decision.approved, decision.reasons))
    return alerts


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Quant options monitor scheduler")
    parser.add_argument("--symbols", nargs="+", required=True)
    parser.add_argument("--mode", choices=["scan"], default="scan")
    parser.add_argument("--config", default="configs/example.yaml")
    args = parser.parse_args(argv)

    config = load_config(args.config)
    router = AlertRouter([ConsoleAlert(), EmailAlert(config.email), TelegramAlert(config.telegram)])
    if args.mode == "scan":
        for body in scan_symbols(args.symbols, config):
            router.send("Quant Options Monitor Alert", body)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
