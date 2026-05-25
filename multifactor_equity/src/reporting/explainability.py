from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


SCORE_COLUMNS = ["composite_score", "momentum_score", "value_score", "quality_score", "low_vol_score"]
MISSING_COLUMNS = ["momentum_missing_count", "value_missing_count", "quality_missing_count", "low_vol_missing_count", "missing_count"]
SUBFACTOR_BASE_COLUMNS = [
    "mom_12_1",
    "mom_6_1",
    "earnings_yield",
    "fcf_yield",
    "book_to_market",
    "sales_to_price",
    "roe",
    "gross_margin",
    "debt_to_equity",
    "accruals",
    "neg_debt_to_equity",
    "neg_accruals",
    "vol_63",
    "vol_126",
    "beta_252",
    "neg_vol_63",
    "neg_vol_126",
    "neg_beta_252",
]


def explanation_columns(factor_scores: pd.DataFrame) -> list[str]:
    cols = ["signal_date", "execution_date", "rebalance_date", "ticker", "sector", "rank", "weight"]
    cols += [c for c in SCORE_COLUMNS + MISSING_COLUMNS if c in factor_scores.columns]
    for base in SUBFACTOR_BASE_COLUMNS:
        cols += [c for c in [base, f"{base}_winsor", f"{base}_sector_z"] if c in factor_scores.columns]
    cols.append("summary")
    return cols


def _top_decile(row: pd.Series, cross: pd.DataFrame, col: str) -> bool:
    if col not in cross or pd.isna(row.get(col)):
        return False
    return row[col] >= cross[col].quantile(0.9)


def _positive(row: pd.Series, col: str) -> bool:
    return col in row and pd.notna(row[col]) and row[col] > 0


def build_summary(row: pd.Series, cross: pd.DataFrame) -> str:
    parts: list[str] = []
    if _top_decile(row, cross, "mom_12_1_sector_z"):
        parts.append("Momentum strong: sector-adjusted mom_12_1 in top decile")
    elif _positive(row, "momentum_score"):
        parts.append("Momentum supportive: combined sector-adjusted momentum is positive")
    else:
        parts.append("Momentum weak: combined sector-adjusted momentum is below average")

    if _positive(row, "roe_sector_z") and _positive(row, "gross_margin_sector_z"):
        parts.append("Quality positive: ROE and gross margin above sector average")
    elif pd.isna(row.get("roe")) or pd.isna(row.get("gross_margin")):
        parts.append("Quality incomplete: ROE or gross margin missing")
    else:
        parts.append("Quality mixed: profitability metrics are not both above sector average")

    if pd.isna(row.get("fcf_yield")):
        parts.append("Value weak: fcf_yield missing")
    elif _positive(row, "value_score"):
        parts.append("Value supportive: aggregate value score is above sector average")
    else:
        parts.append("Value weak: aggregate value score is below sector average")

    if _positive(row, "neg_beta_252_sector_z"):
        parts.append("Low volatility supportive: beta below sector average")
    elif _positive(row, "low_vol_score"):
        parts.append("Low volatility supportive: aggregate low-vol score is positive")
    else:
        parts.append("Low volatility weak: aggregate low-vol score is below average")
    return "; ".join(parts)


def build_decision_explanations(
    factor_scores: pd.DataFrame,
    rebalance_log: pd.DataFrame,
    positions: pd.DataFrame,
) -> pd.DataFrame:
    if factor_scores.empty or rebalance_log.empty or positions.empty:
        return pd.DataFrame(columns=explanation_columns(factor_scores))

    scores = factor_scores.copy().reset_index(drop=True)
    scores["signal_date"] = pd.to_datetime(scores["signal_date"])
    logs = rebalance_log.copy()
    logs["signal_date"] = pd.to_datetime(logs["signal_date"])
    logs["execution_date"] = pd.to_datetime(logs["execution_date"])
    pos = positions.copy()
    pos["date"] = pd.to_datetime(pos["date"])
    rows: list[dict[str, Any]] = []

    for _, log in logs.iterrows():
        signal_date = log["signal_date"]
        execution_date = log["execution_date"]
        cross = scores[scores["signal_date"] == signal_date].copy()
        if cross.empty:
            continue
        cross["rank"] = cross["composite_score"].rank(ascending=False, method="first").astype(int)
        selected = pos[pos["date"] == execution_date][["ticker", "weight"]]
        if selected.empty:
            continue
        selected_scores = cross.merge(selected, on="ticker", how="inner")
        for _, row in selected_scores.iterrows():
            record = row.to_dict()
            record["execution_date"] = execution_date
            record["rebalance_date"] = execution_date
            record["summary"] = build_summary(row, cross)
            rows.append(record)

    out = pd.DataFrame(rows)
    cols = explanation_columns(scores)
    return out.reindex(columns=cols).sort_values(["rebalance_date", "rank", "ticker"]).reset_index(drop=True)


def write_latest_rebalance_json(explanations: pd.DataFrame, path: str | Path) -> None:
    path = Path(path)
    if explanations.empty:
        payload: dict[str, Any] = {"rebalance_date": None, "stocks": []}
    else:
        latest = explanations["rebalance_date"].max()
        latest_rows = explanations[explanations["rebalance_date"] == latest].copy()
        latest_rows = latest_rows.where(pd.notna(latest_rows), None)
        payload = {
            "rebalance_date": pd.Timestamp(latest).date().isoformat(),
            "stocks": latest_rows.to_dict(orient="records"),
        }
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
