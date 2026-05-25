from __future__ import annotations

import numpy as np
import pandas as pd


def generate_order_preview(
    decisions: pd.DataFrame,
    latest_prices: pd.Series,
    portfolio_value: float,
    min_trade_notional: float,
    allow_fractional_shares: bool,
) -> pd.DataFrame:
    rows = []
    trade_decisions = decisions[decisions["decision"].isin(["BUY", "SELL", "ADD", "TRIM"])].copy()
    for _, row in trade_decisions.iterrows():
        ticker = row["ticker"]
        estimated_price = float(latest_prices.get(ticker, np.nan))
        weight_delta = float(row["target_weight"] - row["current_weight"])
        estimated_notional = abs(weight_delta) * portfolio_value
        if pd.isna(estimated_price) or estimated_price <= 0 or estimated_notional < min_trade_notional:
            continue
        raw_share_delta = abs(weight_delta) * portfolio_value / estimated_price
        share_delta = raw_share_delta if allow_fractional_shares else int(np.floor(raw_share_delta))
        if share_delta <= 0:
            continue
        rows.append(
            {
                "ticker": ticker,
                "side": "buy" if weight_delta > 0 else "sell",
                "share_delta": share_delta if weight_delta > 0 else -share_delta,
                "estimated_price": estimated_price,
                "estimated_notional": share_delta * estimated_price,
                "reason_summary": row.get("explanation", ""),
            }
        )
    return pd.DataFrame(rows)
