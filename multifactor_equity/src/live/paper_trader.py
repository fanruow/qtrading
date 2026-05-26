from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from src.live.alpaca_broker import AlpacaPaperBroker
from src.live.broker_interface import BrokerInterface
from src.live.execution_recorder import write_execution_outputs
from src.live.order_builder import build_orders
from src.live.portfolio_sync import current_positions_frame, merge_current_target
from src.live.risk_checks import check_signal_freshness, run_risk_checks
from src.utils.config import project_path


def load_signal_inputs(config: dict) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    source = config["paper_trading"]["signal_source"]
    target = pd.read_csv(project_path(source["target_portfolio_path"]))
    decisions = pd.read_csv(project_path(source["decisions_path"]))
    explanations = pd.read_csv(project_path(source["explanations_path"]))
    if "explanation" not in decisions.columns and "explanation" in explanations.columns:
        decisions = decisions.merge(explanations[["ticker", "explanation"]], on="ticker", how="left")
    return target, decisions, explanations


class PaperTrader:
    def __init__(self, config: dict, broker: BrokerInterface | None = None, output_dir: str | Path | None = None):
        self.config = config
        paper_cfg = config["paper_trading"]
        self.broker = broker or AlpacaPaperBroker(paper=bool(paper_cfg.get("paper", True)))
        self.output_dir = Path(output_dir) if output_dir is not None else project_path("outputs")

    def run(self, dry_run: bool, execute: bool, today: date | None = None) -> dict[str, pd.DataFrame]:
        paper_cfg = self.config["paper_trading"]
        target, decisions, _ = load_signal_inputs(self.config)
        check_signal_freshness(target, paper_cfg["risk"], today=today)
        account = self.broker.get_account()
        positions = self.broker.get_positions()
        current = current_positions_frame(account, positions)
        current_vs_target = merge_current_target(current, target, decisions)
        preview, orders, rejected = build_orders(current_vs_target, account, paper_cfg["execution"], run_date=today)
        run_risk_checks(self.broker, account, current_vs_target, orders, paper_cfg["risk"])

        submitted_rows = []
        if execute:
            if dry_run:
                raise ValueError("--execute requires dry_run=false")
            for order in orders:
                submitted = self.broker.submit_order(order)
                submitted_rows.append({**submitted, "factor_explanation": order.reason_summary})
        submitted = pd.DataFrame(submitted_rows)
        account_log = {"equity": account.equity, "cash": account.cash, "buying_power": account.buying_power}
        write_execution_outputs(self.output_dir, preview, submitted, rejected, current_vs_target, dry_run=dry_run, execute=execute, account=account_log)
        return {
            "orders_preview": preview,
            "submitted_orders": submitted,
            "rejected_orders": rejected,
            "current_vs_target": current_vs_target,
        }
