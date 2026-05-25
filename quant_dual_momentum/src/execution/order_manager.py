"""Order sizing and diff generation utilities."""

from __future__ import annotations

import math

import pandas as pd

from .broker_base import PlannedOrder, Position


def target_weights_to_shares(
    target_weights: pd.Series,
    equity: float,
    latest_prices: pd.Series,
) -> dict[str, int]:
    """Convert target weights into whole-share target quantities."""
    target_shares: dict[str, int] = {}
    for symbol, weight in target_weights.fillna(0.0).items():
        price = float(latest_prices.get(symbol, 0.0))
        if price <= 0 or weight <= 0:
            target_shares[symbol] = 0
            continue
        target_shares[symbol] = int(math.floor(equity * float(weight) / price))
    return target_shares


def positions_to_shares(positions: dict[str, Position], symbols: list[str]) -> dict[str, int]:
    """Convert broker position objects into integer share quantities."""
    return {symbol: int(float(positions.get(symbol, Position(symbol, 0)).qty)) for symbol in symbols}


def generate_order_diff(
    current_shares: dict[str, int],
    target_shares: dict[str, int],
    latest_prices: pd.Series,
    min_order_notional: float = 1.0,
) -> list[PlannedOrder]:
    """Generate buy/sell orders needed to move current shares to target shares."""
    orders: list[PlannedOrder] = []
    symbols = sorted(set(current_shares) | set(target_shares))
    for symbol in symbols:
        delta = int(target_shares.get(symbol, 0) - current_shares.get(symbol, 0))
        if delta == 0:
            continue
        price = float(latest_prices.get(symbol, 0.0))
        if price <= 0:
            continue
        notional = abs(delta) * price
        if notional < min_order_notional:
            continue
        orders.append(
            PlannedOrder(
                symbol=symbol,
                side="buy" if delta > 0 else "sell",
                qty=abs(delta),
                estimated_price=price,
                estimated_notional=notional,
            )
        )
    return orders


def calculate_turnover_from_orders(orders: list[PlannedOrder], equity: float) -> float:
    """Estimate turnover from generated order notionals divided by account equity."""
    if equity <= 0:
        return 0.0
    return float(sum(order.estimated_notional for order in orders) / equity)


def submit_or_print_orders(
    broker,
    orders: list[PlannedOrder],
    dry_run: bool = True,
) -> list[object]:
    """Print orders in dry-run mode or submit them through the broker."""
    if dry_run:
        for order in orders:
            print(
                f"DRY RUN {order.side.upper()} {order.qty} {order.symbol} "
                f"@ ~{order.estimated_price:.2f} notional={order.estimated_notional:.2f}"
            )
        return []
    return [broker.submit_order(order) for order in orders]
