from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from src.backtest.benchmarks import buy_and_hold_returns, equal_weight_returns, sector_neutral_equal_weight_returns
from src.backtest.engine import BacktestEngine
from src.backtest.metrics import performance_metrics
from src.data.fundamental_loader import FundamentalLoader
from src.data.price_loader import make_price_loader
from src.factors.diagnostics import compute_factor_diagnostics
from src.reporting.explainability import build_decision_explanations, write_latest_rebalance_json
from src.reporting.plots import save_drawdown, save_equity_curve, save_factor_ic
from src.utils.config import load_config, project_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.yaml")
    args = parser.parse_args()
    config_path = project_path(args.config)
    config = load_config(config_path)
    output_dir = project_path("outputs")
    output_dir.mkdir(exist_ok=True)

    fundamentals = FundamentalLoader(project_path(config["data"]["fundamentals_path"])).load()
    tickers = list(dict.fromkeys(config["data"]["tickers"] + [config["data"].get("benchmark", "SPY"), "IWB"]))
    prices = make_price_loader(config["data"]["price_source"]).load(tickers, config["start_date"], config["end_date"])
    engine = BacktestEngine(prices.close, prices.volume, fundamentals, config)
    results = engine.run()

    spy_returns = buy_and_hold_returns(prices.close, "SPY")
    results["daily_returns"]["SPY"] = spy_returns.reindex(results["daily_returns"].index).fillna(0.0)
    results["equity_curves"]["SPY"] = (1 + results["daily_returns"]["SPY"]).cumprod() * config["initial_capital"]
    results["daily_returns"]["eligible_equal_weight"] = equal_weight_returns(prices.close, results["universe_members"])
    sector_map = fundamentals.groupby("ticker")["sector"].last().to_dict()
    results["daily_returns"]["eligible_sector_neutral_equal_weight"] = sector_neutral_equal_weight_returns(prices.close, sector_map, results["universe_members"])
    if "IWB" in prices.close:
        results["daily_returns"]["IWB"] = buy_and_hold_returns(prices.close, "IWB")
    for col in [c for c in results["daily_returns"].columns if c not in results["equity_curves"].columns]:
        results["equity_curves"][col] = (1 + results["daily_returns"][col]).cumprod() * config["initial_capital"]

    factor_ic, factor_quantiles = compute_factor_diagnostics(results["factor_scores"], prices.close)
    explanations = build_decision_explanations(results["factor_scores"], results["rebalance_log"], results["positions"])
    turnover = results["rebalance_log"].set_index("execution_date")["turnover"] if not results["rebalance_log"].empty else pd.Series(dtype=float)
    holdings = results["positions"].groupby("date")["ticker"].nunique() if not results["positions"].empty else pd.Series(dtype=float)
    summary = performance_metrics(
        results["daily_returns"]["strategy"],
        results["equity_curves"]["strategy"],
        turnover=turnover,
        holdings=holdings,
        sector_exposure=results["sector_exposure"],
        benchmark_returns=results["daily_returns"]["SPY"],
    )

    outputs = {
        "equity_curves.csv": results["equity_curves"],
        "daily_returns.csv": results["daily_returns"],
        "positions.csv": results["positions"],
        "trades.csv": results["trades"],
        "rebalance_log.csv": results["rebalance_log"],
        "factor_scores.csv": results["factor_scores"],
        "factor_ic.csv": factor_ic,
        "factor_quantile_returns.csv": factor_quantiles,
        "decision_explanations.csv": explanations,
        "performance_summary.csv": summary.to_frame("value"),
        "sector_exposure.csv": results["sector_exposure"],
    }
    for name, df in outputs.items():
        df.to_csv(output_dir / name, index=True)
    write_latest_rebalance_json(explanations, output_dir / "latest_rebalance_explanations.json")
    save_equity_curve(results["equity_curves"], output_dir / "equity_curve.png")
    save_drawdown(results["equity_curves"]["strategy"], output_dir / "drawdown.png")
    save_factor_ic(factor_ic, output_dir / "factor_ic.png")
    print(f"Wrote outputs to {output_dir}")


if __name__ == "__main__":
    main()
