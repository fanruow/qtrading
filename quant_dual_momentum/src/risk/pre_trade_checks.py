"""Pre-trade risk checks for generated orders."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.execution.broker_base import AccountSnapshot, PlannedOrder, Position
from src.execution.order_manager import calculate_turnover_from_orders
from .limits import LiveConfig


@dataclass(frozen=True)
class RiskCheckResult:
    """Result of pre-trade validation."""

    passed: bool
    errors: list[str]


def is_latest_trading_data(data_date: pd.Timestamp, today: pd.Timestamp | None = None, max_age_days: int = 5) -> bool:
    """Return True when the latest market data is plausibly current."""
    current = (today or pd.Timestamp.today()).normalize()
    latest = pd.Timestamp(data_date).normalize()
    return 0 <= (current - latest).days <= max_age_days


def run_pre_trade_checks(
    config: LiveConfig,
    account: AccountSnapshot | None,
    positions: dict[str, Position] | None,
    target_weights: pd.Series,
    orders: list[PlannedOrder],
    latest_data_date: pd.Timestamp,
    today: pd.Timestamp | None = None,
) -> RiskCheckResult:
    """Run pre-trade checks and return all blocking errors."""
    errors: list[str] = []

    if account is None or account.equity <= 0:
        errors.append("Account equity is unavailable or non-positive.")
    if positions is None:
        errors.append("Current positions are unavailable.")
    if not is_latest_trading_data(latest_data_date, today=today):
        errors.append(f"Market data is stale: latest data date is {latest_data_date.date()}.")
    if len(orders) > len(config.symbols):
        errors.append("Generated order count exceeds symbol universe size.")
    if not config.dry_run:
        if not config.paper:
            errors.append("paper=False is not allowed.")
    else:
        pass

    gross_exposure = float(target_weights.abs().sum())
    if gross_exposure > config.max_total_gross_exposure:
        errors.append("Total target gross exposure exceeds max_total_gross_exposure.")

    oversized_positions = target_weights[target_weights.abs() > config.max_position_weight]
    if not oversized_positions.empty:
        errors.append("Target position weight exceeds max_position_weight.")

    oversized_orders = [order for order in orders if order.estimated_notional > config.max_order_notional]
    if oversized_orders:
        errors.append("Generated order notional exceeds max_order_notional.")

    if account is not None and positions is not None:
        turnover = calculate_turnover_from_orders(orders, account.equity)
        if turnover > config.max_daily_turnover:
            errors.append("Estimated daily turnover exceeds max_daily_turnover.")

    return RiskCheckResult(passed=not errors, errors=errors)
