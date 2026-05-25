"""Command-line entrypoint for ETF dual momentum backtest."""

from __future__ import annotations

from datetime import date

import pandas as pd

from src.backtest import run_dual_momentum_backtest
from src.benchmarks import build_benchmark_returns
from src.data import download_adjusted_close
from src.metrics import performance_summary
from src.plotting import plot_drawdowns, plot_equity_curves
from src.utils import ensure_dir


CONFIG = {
    "tickers": ["SPY", "QQQ", "IWM", "EFA", "EEM", "TLT", "IEF", "GLD", "VNQ", "DBC"],
    "start": "2007-01-01",
    "end": None,
    "top_n": 3,
    "short_lag": 21,
    "long_lag": 252,
    "ma_window": 200,
    "vol_window": 63,
    "target_volatility": 0.10,
    "transaction_cost_rate": 0.001,
    "outputs_dir": "outputs",
}


def main() -> None:
    """Download data, run backtest, calculate metrics, and save outputs."""
    outputs_dir = ensure_dir(CONFIG["outputs_dir"])
    end = CONFIG["end"] or date.today().isoformat()

    prices = download_adjusted_close(CONFIG["tickers"], start=CONFIG["start"], end=end)
    strategy = run_dual_momentum_backtest(
        prices=prices,
        top_n=CONFIG["top_n"],
        target_volatility=CONFIG["target_volatility"],
        vol_window=CONFIG["vol_window"],
        transaction_cost_rate=CONFIG["transaction_cost_rate"],
        short_lag=CONFIG["short_lag"],
        long_lag=CONFIG["long_lag"],
        ma_window=CONFIG["ma_window"],
    )

    benchmark_returns = build_benchmark_returns(prices, CONFIG["tickers"])
    all_returns = pd.concat([strategy["returns"], benchmark_returns], axis=1).fillna(0.0)
    equity_curves = (1.0 + all_returns).cumprod()
    summary = performance_summary(all_returns, strategy["rebalance_log"])

    equity_curves.to_csv(outputs_dir / "equity_curves.csv")
    strategy["weights"].to_csv(outputs_dir / "weights.csv")
    strategy["rebalance_log"].to_csv(outputs_dir / "rebalance_log.csv", index=False)
    summary.to_csv(outputs_dir / "performance_summary.csv")
    plot_equity_curves(equity_curves, outputs_dir / "equity_curve.png")
    plot_drawdowns(equity_curves, outputs_dir / "drawdown.png")

    print("Backtest complete.")
    print(f"Date range: {prices.index.min().date()} to {prices.index.max().date()}")
    print(f"Outputs written to: {outputs_dir.resolve()}")
    print(summary.round(4).to_string())


if __name__ == "__main__":
    main()
