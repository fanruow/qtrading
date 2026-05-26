from __future__ import annotations

import math
from datetime import date

import pandas as pd

from src.live.broker_interface import BrokerAccount, LiveOrder


def build_orders(
    current_vs_target: pd.DataFrame,
    account: BrokerAccount,
    execution_config: dict,
    strategy_name: str = "multifactor",
    run_date: date | None = None,
) -> tuple[pd.DataFrame, list[LiveOrder], pd.DataFrame]:
    run_date = run_date or date.today()
    min_notional = float(execution_config["min_trade_notional"])
    min_weight_change = float(execution_config["min_weight_change"])
    allow_fractional = bool(execution_config["allow_fractional_shares"])
    order_type = execution_config["order_type"]
    tif = execution_config["time_in_force"]
    preview_rows = []
    orders = []
    rejected = []
    for _, row in current_vs_target.iterrows():
        ticker = row["ticker"]
        weight_delta = float(row["weight_delta"])
        notional = abs(weight_delta) * account.equity
        if abs(weight_delta) < min_weight_change:
            rejected.append({**row.to_dict(), "reject_reason": "below_min_weight_change"})
            continue
        if notional < min_notional:
            rejected.append({**row.to_dict(), "reject_reason": "below_min_trade_notional"})
            continue
        price = notional / max(1.0, abs(weight_delta) * account.equity / max(notional, 1.0))
        estimated_price = float(row.get("estimated_price", 1.0) or 1.0)
        qty = notional / estimated_price
        if not allow_fractional:
            qty = math.floor(qty)
        if qty <= 0:
            rejected.append({**row.to_dict(), "reject_reason": "zero_quantity"})
            continue
        side = "buy" if weight_delta > 0 else "sell"
        client_order_id = f"{strategy_name}-{run_date.isoformat()}-{ticker}".replace("_", "-")[:48]
        reason = row.get("explanation", "") if pd.notna(row.get("explanation", "")) else ""
        preview_rows.append(
            {
                "ticker": ticker,
                "side": side,
                "share_delta": qty if side == "buy" else -qty,
                "qty": qty,
                "estimated_notional": notional,
                "weight_delta": weight_delta,
                "decision": row.get("decision", ""),
                "client_order_id": client_order_id,
                "reason_summary": reason,
            }
        )
        orders.append(
            LiveOrder(
                ticker=ticker,
                side=side,
                qty=qty,
                order_type=order_type,
                time_in_force=tif,
                client_order_id=client_order_id,
                decision=row.get("decision", ""),
                reason_summary=reason,
            )
        )
    preview = pd.DataFrame(preview_rows)
    if bool(execution_config.get("sell_before_buy", True)) and not preview.empty:
        order_rank = preview["side"].map({"sell": 0, "buy": 1})
        preview = preview.assign(_order_rank=order_rank).sort_values(["_order_rank", "ticker"]).drop(columns="_order_rank").reset_index(drop=True)
        order_map = {order.client_order_id: order for order in orders}
        orders = [order_map[row["client_order_id"]] for _, row in preview.iterrows()]
    return preview, orders, pd.DataFrame(rejected)
