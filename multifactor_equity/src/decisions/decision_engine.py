from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from src.decisions.explanations import attach_explanations
from src.decisions.order_preview import generate_order_preview
from src.decisions.schemas import DecisionConfig
from src.utils.config import project_path
from src.utils.validation import require_columns


CURRENT_POSITION_COLUMNS = ["ticker", "current_weight", "current_shares"]


def load_current_positions(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    require_columns(df, CURRENT_POSITION_COLUMNS, "current_positions")
    return df


def latest_signal_date(factor_scores: pd.DataFrame, as_of_date: str) -> pd.Timestamp:
    scores = factor_scores.copy()
    scores["signal_date"] = pd.to_datetime(scores["signal_date"])
    if as_of_date == "latest":
        return pd.Timestamp(scores["signal_date"].max())
    return pd.Timestamp(as_of_date)


def classify_decision(current_weight: float, target_weight: float, min_weight_change: float) -> str:
    if current_weight == 0 and target_weight > 0:
        return "BUY"
    if current_weight > 0 and target_weight == 0:
        return "SELL"
    diff = target_weight - current_weight
    if diff > min_weight_change:
        return "ADD"
    if -diff > min_weight_change:
        return "TRIM"
    return "HOLD"


def build_current_vs_target(
    current_positions: pd.DataFrame,
    target_weights: pd.Series,
    factor_scores: pd.DataFrame,
    top_n: int,
    min_weight_change: float,
) -> pd.DataFrame:
    current = current_positions.set_index("ticker")
    current_weights = current["current_weight"].astype(float)
    current_shares = current["current_shares"].astype(float)
    scores = factor_scores.copy().reset_index(drop=True)
    scores["rank"] = scores["composite_score"].rank(ascending=False, method="first").astype(int)
    target_weights = target_weights.astype(float)
    tickers = current_weights.index.union(target_weights.index)
    skip_candidates = scores[(scores["rank"] <= top_n) & (~scores["ticker"].isin(target_weights.index))]
    tickers = tickers.union(pd.Index(skip_candidates["ticker"]))

    rows = []
    for ticker in tickers:
        current_weight = float(current_weights.get(ticker, 0.0))
        target_weight = float(target_weights.get(ticker, 0.0))
        if ticker in set(skip_candidates["ticker"]) and current_weight == 0 and target_weight == 0:
            decision = "SKIP"
        else:
            decision = classify_decision(current_weight, target_weight, min_weight_change)
        score_row = scores[scores["ticker"] == ticker]
        rows.append(
            {
                "ticker": ticker,
                "current_weight": current_weight,
                "target_weight": target_weight,
                "weight_delta": target_weight - current_weight,
                "current_shares": float(current_shares.get(ticker, 0.0)),
                "rank": int(score_row["rank"].iloc[0]) if not score_row.empty else pd.NA,
                "decision": decision,
            }
        )
    return pd.DataFrame(rows).sort_values(["decision", "rank", "ticker"], na_position="last").reset_index(drop=True)


def write_decision_json(decisions: pd.DataFrame, path: str | Path, signal_date: pd.Timestamp) -> None:
    clean = decisions.where(pd.notna(decisions), None)
    payload = {"signal_date": signal_date.date().isoformat(), "decisions": clean.to_dict(orient="records")}
    Path(path).write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def run_decision_output(
    results: dict,
    close: pd.DataFrame,
    config: dict,
    output_dir: str | Path,
) -> dict[str, pd.DataFrame | Path | dict[str, int]]:
    output_dir = Path(output_dir)
    decision_cfg = config.get("decision_output", {})
    signal_date = latest_signal_date(results["factor_scores"], str(decision_cfg.get("as_of_date", "latest")))
    factor_scores = results["factor_scores"].copy().reset_index(drop=True)
    factor_scores["signal_date"] = pd.to_datetime(factor_scores["signal_date"])
    latest_scores = factor_scores[factor_scores["signal_date"] == signal_date].copy()

    rebalance_log = results["rebalance_log"].copy()
    rebalance_log["signal_date"] = pd.to_datetime(rebalance_log["signal_date"])
    latest_exec_date = pd.Timestamp(rebalance_log.loc[rebalance_log["signal_date"] == signal_date, "execution_date"].iloc[-1])
    positions = results["positions"].copy()
    positions["date"] = pd.to_datetime(positions["date"])
    latest_target = positions[positions["date"] == latest_exec_date].set_index("ticker")["weight"]
    latest_target_portfolio = latest_target.rename("target_weight").reset_index()
    latest_target_portfolio = latest_target_portfolio.merge(latest_scores[["ticker", "sector"]], on="ticker", how="left")
    latest_target_portfolio["signal_date"] = signal_date
    latest_target_portfolio["execution_date"] = latest_exec_date

    current_path = project_path(config["portfolio"]["current_positions_path"])
    current_positions = load_current_positions(current_path)
    order_cfg = config.get("orders", {})
    decision_config = DecisionConfig(
        min_weight_change=float(order_cfg.get("min_weight_change", 0.0)),
        min_trade_notional=float(order_cfg.get("min_trade_notional", 0.0)),
        allow_fractional_shares=bool(order_cfg.get("allow_fractional_shares", False)),
        portfolio_value=float(config["portfolio"].get("portfolio_value", config.get("initial_capital", 0))),
    )
    current_vs_target = build_current_vs_target(
        current_positions,
        latest_target,
        latest_scores,
        int(config["portfolio"]["top_n"]),
        decision_config.min_weight_change,
    )

    decisions = current_vs_target.copy()
    if decision_cfg.get("include_explanations", True):
        decisions = attach_explanations(decisions, latest_scores, config["factors"]["weights"])

    output_dir.mkdir(exist_ok=True)
    latest_target_portfolio.to_csv(output_dir / "latest_target_portfolio.csv", index=False)
    current_vs_target.to_csv(output_dir / "current_vs_target.csv", index=False)
    decisions.to_csv(output_dir / "latest_decisions.csv", index=False)
    explanations = decisions[decisions.columns].copy()
    explanations.to_csv(output_dir / "decision_explanations.csv", index=False)
    write_decision_json(decisions, output_dir / "latest_decisions.json", signal_date)

    orders_preview = pd.DataFrame()
    if decision_cfg.get("include_order_preview", True) and order_cfg.get("generate_preview", True):
        latest_prices = close.loc[:latest_exec_date].iloc[-1]
        orders_preview = generate_order_preview(
            decisions,
            latest_prices,
            decision_config.portfolio_value,
            decision_config.min_trade_notional,
            decision_config.allow_fractional_shares,
        )
        orders_preview.to_csv(output_dir / "orders_preview.csv", index=False)

    counts = decisions["decision"].value_counts().to_dict()
    return {
        "decisions": decisions,
        "current_vs_target": current_vs_target,
        "latest_target_portfolio": latest_target_portfolio,
        "orders_preview": orders_preview,
        "counts": counts,
    }
