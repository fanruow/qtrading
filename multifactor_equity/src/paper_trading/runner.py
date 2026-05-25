from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from src.paper_trading.broker import Account, BrokerInterface
from src.paper_trading.orders import build_orders_preview, order_requests_from_preview
from src.paper_trading.risk import validate_paper_targets
from src.portfolio.rebalance import build_target_weights
from src.reporting.explainability import build_summary


def latest_factor_scores(factor_scores: pd.DataFrame) -> pd.DataFrame:
    scores = factor_scores.copy()
    if "ticker" not in scores.columns and scores.index.name == "ticker":
        scores = scores.reset_index()
    scores["signal_date"] = pd.to_datetime(scores["signal_date"])
    latest = scores["signal_date"].max()
    return scores[scores["signal_date"] == latest].copy()


def explain_latest_targets(latest_scores: pd.DataFrame, target_weights: pd.Series) -> pd.DataFrame:
    cross = latest_scores.copy().reset_index(drop=True)
    cross["rank"] = cross["composite_score"].rank(ascending=False, method="first").astype(int)
    selected = cross[cross["ticker"].isin(target_weights.index)].copy()
    selected["weight"] = selected["ticker"].map(target_weights)
    selected["summary"] = [build_summary(row, cross) for _, row in selected.iterrows()]
    return selected[["signal_date", "ticker", "sector", "rank", "weight", "composite_score", "momentum_score", "value_score", "quality_score", "low_vol_score", "missing_count", "summary"]]


class StaticPaperBroker(BrokerInterface):
    def __init__(self, account: Account, known_symbols: set[str]):
        self.account = account
        self.known_symbols = known_symbols

    def get_account(self) -> Account:
        return self.account

    def get_positions(self) -> list:
        return []

    def get_tradable_symbols(self) -> set[str]:
        return self.known_symbols

    def submit_order(self, order):
        raise RuntimeError("StaticPaperBroker cannot submit orders")


class PaperTradingRunner:
    def __init__(
        self,
        config: dict[str, Any],
        broker: BrokerInterface | None = None,
        output_dir: str | Path = "outputs",
    ):
        self.config = config
        self.output_dir = Path(output_dir)
        paper_cfg = config.get("paper_trading", {})
        self.dry_run = bool(paper_cfg.get("dry_run", True))
        self.execute = bool(paper_cfg.get("execute", False))
        self.cash_buffer = float(paper_cfg.get("cash_buffer", 0.02))
        self.min_notional = float(paper_cfg.get("min_notional", 1.0))
        self.broker = broker

    def run_from_factor_scores(self, factor_scores: pd.DataFrame) -> dict[str, pd.DataFrame]:
        latest_scores = latest_factor_scores(factor_scores)
        max_stock_weight = self.config["portfolio"]["max_stock_weight"]
        max_sector_weight = self.config["portfolio"]["max_sector_weight"]
        indexed_scores = latest_scores.set_index("ticker", drop=False)
        raw_targets = build_target_weights(indexed_scores, self.config["portfolio"])
        target_weights = raw_targets * max(0.0, 1.0 - self.cash_buffer)
        explanations = explain_latest_targets(latest_scores, target_weights)

        broker = self.broker or StaticPaperBroker(
            Account(equity=float(self.config.get("initial_capital", 1_000_000)), cash=float(self.config.get("initial_capital", 1_000_000))),
            known_symbols=set(latest_scores["ticker"]),
        )
        account = broker.get_account()
        positions = broker.get_positions()
        known_symbols = broker.get_tradable_symbols()
        validate_paper_targets(target_weights, latest_scores, known_symbols, max_stock_weight, max_sector_weight, self.cash_buffer)

        preview = build_orders_preview(target_weights, account, positions, explanations, self.min_notional)
        self.output_dir.mkdir(exist_ok=True)
        preview.to_csv(self.output_dir / "orders_preview.csv", index=False)
        explanations.to_csv(self.output_dir / "paper_order_explanations.csv", index=False)

        submitted = []
        if self.execute:
            if self.dry_run:
                raise ValueError("paper trading execute=true requires dry_run=false")
            for order in order_requests_from_preview(preview):
                submitted.append(broker.submit_order(order))
        return {"orders_preview": preview, "paper_order_explanations": explanations, "submitted_orders": pd.DataFrame(submitted)}
