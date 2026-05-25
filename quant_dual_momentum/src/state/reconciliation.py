"""Position reconciliation helpers."""

from __future__ import annotations

from src.execution.broker_base import PlannedOrder, Position


def symbols_with_unmatched_targets(
    positions: dict[str, Position],
    orders: list[PlannedOrder],
    symbols: list[str],
) -> list[str]:
    """Return symbols touched by generated orders or existing positions."""
    touched = {order.symbol for order in orders}
    held = {symbol for symbol, position in positions.items() if position.qty != 0}
    return sorted((touched | held) & set(symbols))
