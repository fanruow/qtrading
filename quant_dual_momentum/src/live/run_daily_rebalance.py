"""Daily paper trading rebalance runner.

Run with:
    python -m src.live.run_daily_rebalance --dry-run
    python -m src.live.run_daily_rebalance --paper --execute
"""

from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd
import yaml

from src.data import download_adjusted_close
from src.execution.alpaca_broker import AlpacaBroker
from src.execution.order_manager import (
    generate_order_diff,
    positions_to_shares,
    submit_or_print_orders,
    target_weights_to_shares,
)
from src.portfolio import apply_volatility_scale, calculate_realized_volatility, calculate_volatility_scale
from src.risk.kill_switch import is_kill_switch_active
from src.risk.limits import LiveConfig, require_paper_trading
from src.risk.pre_trade_checks import run_pre_trade_checks
from src.signals import generate_latest_target_weights
from src.state.store import append_live_orders_csv, write_run_log
from src.utils import ensure_dir


def load_config(path: str | Path = "config.yaml") -> LiveConfig:
    """Load and validate live paper trading config.yaml."""
    with Path(path).open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}
    return LiveConfig(**payload)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Run ETF dual momentum paper rebalance.")
    parser.add_argument("--config", default="config.yaml", help="Path to config.yaml")
    parser.add_argument("--dry-run", action="store_true", help="Only print planned orders.")
    parser.add_argument("--paper", action="store_true", help="Use Alpaca paper trading.")
    parser.add_argument("--execute", action="store_true", help="Submit orders when paper trading is enabled.")
    return parser.parse_args()


def apply_cli_overrides(config: LiveConfig, args: argparse.Namespace) -> LiveConfig:
    """Apply conservative CLI overrides to validated config."""
    updates = {}
    if args.dry_run:
        updates["dry_run"] = True
    if args.paper:
        updates["paper"] = True
    if args.execute:
        updates["dry_run"] = False
    return copy_config(config, updates)


def copy_config(config: LiveConfig, updates: dict[str, object]) -> LiveConfig:
    """Copy a pydantic config in a way that supports v1 and v2."""
    if hasattr(config, "model_copy"):
        return config.model_copy(update=updates)
    return config.copy(update=updates)


def run_rebalance(config: LiveConfig) -> dict[str, object]:
    """Run one paper trading rebalance cycle."""
    require_paper_trading(config.paper)
    if not config.dry_run and not config.paper:
        raise ValueError("Order execution requires paper=True.")
    if is_kill_switch_active():
        raise RuntimeError("Kill switch is active. Refusing to generate or submit orders.")

    timestamp = datetime.now(timezone.utc).isoformat()
    submitted_orders: list[object] = []
    generated_orders = []
    errors: list[str] = []
    account = None
    positions = None
    target_weights = None

    broker = AlpacaBroker(paper=config.paper)

    try:
        account = broker.get_account()
    except Exception as exc:
        errors.append(f"Failed to read account equity: {exc}")
    try:
        positions = broker.get_positions()
    except Exception as exc:
        errors.append(f"Failed to read current positions: {exc}")

    end = date.today().isoformat()
    prices = download_adjusted_close(config.symbols, start=config.start, end=end)
    latest_prices = prices.iloc[-1].dropna()
    target_weights = generate_latest_target_weights(prices, top_n=config.top_n)
    target_weights = target_weights.reindex(config.symbols).fillna(0.0)
    target_weights = apply_live_volatility_target(
        target_weights,
        prices,
        target_volatility=config.target_vol,
        vol_window=config.vol_window,
    )

    if account is not None and positions is not None:
        target_shares = target_weights_to_shares(target_weights, account.equity, latest_prices)
        current_shares = positions_to_shares(positions, config.symbols)
        generated_orders = generate_order_diff(
            current_shares,
            target_shares,
            latest_prices,
            min_order_notional=config.min_order_notional,
        )

    risk = run_pre_trade_checks(
        config=config,
        account=account,
        positions=positions,
        target_weights=target_weights,
        orders=generated_orders,
        latest_data_date=prices.index[-1],
    )
    errors.extend(risk.errors)

    if errors:
        print("Pre-trade checks failed. No orders submitted.")
        for error in errors:
            print(f"- {error}")
    else:
        submitted_orders = submit_or_print_orders(broker, generated_orders, dry_run=config.dry_run)

    ensure_dir(config.outputs_dir)
    append_live_orders_csv(
        Path(config.outputs_dir) / "live_orders.csv",
        timestamp=timestamp,
        orders=generated_orders,
        submitted=bool(submitted_orders),
    )
    log_path = write_run_log(
        logs_dir=config.logs_dir,
        account_equity=None if account is None else account.equity,
        current_positions=positions,
        target_weights=target_weights,
        generated_orders=generated_orders,
        submitted_orders=submitted_orders,
        errors=errors,
    )
    print(f"Run log written to {log_path}")

    return {
        "orders": generated_orders,
        "submitted_orders": submitted_orders,
        "errors": errors,
        "target_weights": target_weights,
    }


def apply_live_volatility_target(
    raw_target_weights: pd.Series,
    prices: pd.DataFrame,
    target_volatility: float,
    vol_window: int,
) -> pd.Series:
    """Scale latest target weights using trailing basket volatility."""
    returns = prices.pct_change(fill_method=None).fillna(0.0)
    aligned_weights = raw_target_weights.reindex(returns.columns).fillna(0.0)
    basket_returns = (returns * aligned_weights).sum(axis=1)
    realized_vol = calculate_realized_volatility(basket_returns, window=vol_window).iloc[-1]
    scale = calculate_volatility_scale(pd.Series([realized_vol]), target_volatility=target_volatility).iloc[0]
    scaled = apply_volatility_scale(raw_target_weights, scale)
    scaled.name = raw_target_weights.name
    return scaled


def main() -> None:
    """CLI entrypoint for one rebalance cycle."""
    args = parse_args()
    config = apply_cli_overrides(load_config(args.config), args)
    if not args.execute:
        config = copy_config(config, {"dry_run": True})
    run_rebalance(config)


if __name__ == "__main__":
    main()
