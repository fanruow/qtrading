from __future__ import annotations

import pandas as pd

from src.paper_trading.broker import Account, OrderRequest, Position


def build_orders_preview(
    target_weights: pd.Series,
    account: Account,
    positions: list[Position],
    explanations: pd.DataFrame,
    min_notional: float = 1.0,
) -> pd.DataFrame:
    current_value = pd.Series({p.symbol: p.market_value for p in positions}, dtype=float)
    symbols = target_weights.index.union(current_value.index)
    current_weight = current_value.reindex(symbols, fill_value=0.0) / account.equity
    target = target_weights.reindex(symbols, fill_value=0.0)
    delta_weight = target - current_weight
    preview = pd.DataFrame(
        {
            "ticker": symbols,
            "current_weight": current_weight.values,
            "target_weight": target.values,
            "delta_weight": delta_weight.values,
        }
    )
    preview["notional"] = preview["delta_weight"].abs() * account.equity
    preview["side"] = preview["delta_weight"].map(lambda x: "buy" if x > 0 else "sell")
    preview = preview[preview["notional"] >= min_notional].copy()
    if not explanations.empty:
        preview = preview.merge(explanations[["ticker", "summary"]], on="ticker", how="left")
    else:
        preview["summary"] = ""
    return preview.sort_values(["side", "ticker"]).reset_index(drop=True)


def order_requests_from_preview(preview: pd.DataFrame) -> list[OrderRequest]:
    return [
        OrderRequest(symbol=row["ticker"], side=row["side"], notional=float(row["notional"]))
        for _, row in preview.iterrows()
        if float(row["notional"]) > 0
    ]
