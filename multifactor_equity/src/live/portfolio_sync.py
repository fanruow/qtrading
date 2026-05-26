from __future__ import annotations

import pandas as pd

from src.live.broker_interface import BrokerAccount, BrokerPosition


def current_positions_frame(account: BrokerAccount, positions: list[BrokerPosition]) -> pd.DataFrame:
    rows = []
    for position in positions:
        rows.append(
            {
                "ticker": position.ticker,
                "current_market_value": position.market_value,
                "current_shares": position.qty,
                "current_weight": position.market_value / account.equity if account.equity else 0.0,
            }
        )
    return pd.DataFrame(rows, columns=["ticker", "current_market_value", "current_shares", "current_weight"])


def merge_current_target(current: pd.DataFrame, target: pd.DataFrame, decisions: pd.DataFrame) -> pd.DataFrame:
    target_cols = ["ticker", "target_weight"] + (["sector"] if "sector" in target.columns else [])
    target = target[target_cols].copy()
    current = current[["ticker", "current_weight", "current_shares"]].copy()
    merged = current.merge(target, on="ticker", how="outer")
    for col in ["current_weight", "current_shares", "target_weight"]:
        merged[col] = pd.to_numeric(merged[col], errors="coerce").fillna(0.0)
    decision_cols = ["ticker", "decision", "explanation", "sector"]
    available = [c for c in decision_cols if c in decisions.columns]
    merged = merged.merge(decisions[available].drop_duplicates("ticker"), on="ticker", how="left")
    if "sector_x" in merged.columns or "sector_y" in merged.columns:
        merged["sector"] = merged.get("sector_x", pd.Series(index=merged.index, dtype=object)).combine_first(
            merged.get("sector_y", pd.Series(index=merged.index, dtype=object))
        )
        merged = merged.drop(columns=[c for c in ["sector_x", "sector_y"] if c in merged.columns])
    merged["weight_delta"] = merged["target_weight"] - merged["current_weight"]
    merged["decision"] = merged["decision"].fillna("SELL").where(merged["target_weight"] == 0, merged["decision"].fillna("BUY"))
    return merged.sort_values("ticker").reset_index(drop=True)
