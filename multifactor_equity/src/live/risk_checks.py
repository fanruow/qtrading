from __future__ import annotations

from datetime import date

import pandas as pd

from src.live.broker_interface import BrokerAccount, BrokerInterface, LiveOrder


def check_signal_freshness(target: pd.DataFrame, risk_config: dict, today: date | None = None) -> None:
    if not bool(risk_config.get("reject_if_stale_signal", True)):
        return
    if "signal_date" not in target.columns:
        raise ValueError("stale signal check failed: target portfolio missing signal_date")
    today = today or date.today()
    signal_date = pd.to_datetime(target["signal_date"]).max().date()
    age = (today - signal_date).days
    if age > int(risk_config["max_signal_age_days"]):
        raise ValueError(f"stale signal rejected: signal age {age} days exceeds max_signal_age_days")


def run_risk_checks(
    broker: BrokerInterface,
    account: BrokerAccount,
    current_vs_target: pd.DataFrame,
    orders: list[LiveOrder],
    risk_config: dict,
) -> None:
    broker.assert_paper()
    if bool(risk_config.get("reject_if_market_closed", True)) and not broker.is_market_open():
        raise ValueError("market is closed; refusing to submit paper orders")
    if bool(risk_config.get("long_only", True)) and (current_vs_target["target_weight"] < -1e-12).any():
        raise ValueError("long-only risk check failed")
    if current_vs_target["target_weight"].max() > float(risk_config["max_single_name_weight"]) + 1e-12:
        raise ValueError("max_single_name_weight risk check failed")
    if "sector" in current_vs_target.columns and current_vs_target["sector"].notna().any():
        sector_exposure = current_vs_target.groupby("sector")["target_weight"].sum()
        if sector_exposure.max() > float(risk_config["max_sector_weight"]) + 1e-12:
            raise ValueError("max_sector_weight risk check failed")
    gross = current_vs_target["target_weight"].abs().sum()
    max_gross = float(risk_config["max_gross_exposure"])
    cash_buffer = float(risk_config.get("cash_buffer_pct", 0.0))
    if gross > min(max_gross, 1.0 - cash_buffer) + 1e-12:
        raise ValueError("max_gross_exposure or cash buffer risk check failed")
    turnover = current_vs_target["weight_delta"].abs().sum()
    if turnover > float(risk_config["max_turnover_per_run"]) + 1e-12:
        raise ValueError("max_turnover_per_run risk check failed")
    if len(orders) > int(risk_config["max_orders_per_run"]):
        raise ValueError("max_orders_per_run risk check failed")
    if bool(risk_config.get("block_short_sales", True)):
        current_shares = current_vs_target.set_index("ticker")["current_shares"].to_dict()
        for order in orders:
            if order.side == "sell" and order.qty > float(current_shares.get(order.ticker, 0.0)) + 1e-12:
                raise ValueError(f"short sale blocked for {order.ticker}")
