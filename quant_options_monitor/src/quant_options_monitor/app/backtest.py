"""Command-line equity signal backtest."""

from __future__ import annotations

import argparse
from typing import Sequence

from quant_options_monitor.app.scheduler import MockMarketDataProvider
from quant_options_monitor.backtest.equity_backtester import EquitySignalBacktester
from quant_options_monitor.data.yfinance_provider import YFinanceMarketDataProvider


def load_price_history(symbol: str, period: str):
    try:
        return YFinanceMarketDataProvider().get_price_history(symbol, period=period, interval="1d")
    except Exception:
        return MockMarketDataProvider().get_price_history(symbol, period=period, interval="1d")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Backtest equity signal strategy")
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--period", default="5y")
    parser.add_argument("--transaction-cost-bps", type=float, default=1.0)
    parser.add_argument("--long-only", action="store_true")
    args = parser.parse_args(argv)

    prices = load_price_history(args.symbol, args.period)
    result = EquitySignalBacktester(
        transaction_cost_bps=args.transaction_cost_bps,
        allow_short=not args.long_only,
    ).run(args.symbol, prices)

    print(f"Backtest: {args.symbol.upper()} period={args.period}")
    for name, value in result.metrics.items():
        if isinstance(value, float):
            print(f"{name}: {value:.6f}")
        else:
            print(f"{name}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
