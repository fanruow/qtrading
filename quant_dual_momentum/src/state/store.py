"""Persistent run logging for paper trading operations."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from src.execution.broker_base import PlannedOrder, Position
from src.utils import ensure_dir


def order_to_dict(order: PlannedOrder) -> dict[str, Any]:
    """Convert a planned order to a JSON/CSV-friendly dictionary."""
    return {
        "symbol": order.symbol,
        "side": order.side,
        "qty": order.qty,
        "estimated_price": order.estimated_price,
        "estimated_notional": order.estimated_notional,
    }


def position_to_dict(position: Position) -> dict[str, Any]:
    """Convert a position to a JSON-friendly dictionary."""
    return {
        "symbol": position.symbol,
        "qty": position.qty,
        "market_value": position.market_value,
    }


def append_live_orders_csv(
    output_path: str | Path,
    timestamp: str,
    orders: list[PlannedOrder],
    submitted: bool,
) -> None:
    """Append generated order rows to outputs/live_orders.csv."""
    path = Path(output_path)
    ensure_dir(path.parent)
    rows = [
        {
            "timestamp": timestamp,
            "symbol": order.symbol,
            "side": order.side,
            "qty": order.qty,
            "estimated_price": order.estimated_price,
            "estimated_notional": order.estimated_notional,
            "submitted": submitted,
        }
        for order in orders
    ]
    if not rows:
        rows = [{"timestamp": timestamp, "submitted": submitted}]
    frame = pd.DataFrame(rows)
    frame.to_csv(path, mode="a", header=not path.exists(), index=False)


def write_run_log(
    logs_dir: str | Path,
    account_equity: float | None,
    current_positions: dict[str, Position] | None,
    target_weights: pd.Series | None,
    generated_orders: list[PlannedOrder],
    submitted_orders: list[object],
    errors: list[str],
) -> Path:
    """Write a detailed JSON log for one live paper trading run."""
    directory = ensure_dir(logs_dir)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = directory / f"run_{timestamp}.json"
    payload = {
        "timestamp": timestamp,
        "account_equity": account_equity,
        "current_positions": {
            symbol: position_to_dict(position) for symbol, position in (current_positions or {}).items()
        },
        "target_weights": {} if target_weights is None else target_weights.to_dict(),
        "generated_orders": [order_to_dict(order) for order in generated_orders],
        "submitted_orders": [str(order) for order in submitted_orders],
        "errors": errors,
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path
