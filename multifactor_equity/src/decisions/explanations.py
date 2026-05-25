from __future__ import annotations

import json

import pandas as pd

from src.decisions.schemas import SCORE_COLUMNS


def factor_contributions(row: pd.Series, factor_weights: dict[str, float]) -> dict[str, float]:
    contributions = {}
    for score_col in SCORE_COLUMNS:
        if score_col in row and pd.notna(row[score_col]):
            contributions[score_col] = float(row[score_col]) * float(factor_weights.get(score_col, 0.0))
    return contributions


def build_factor_explanation(row: pd.Series, factor_weights: dict[str, float]) -> dict:
    contributions = factor_contributions(row, factor_weights)
    sorted_items = sorted(contributions.items(), key=lambda item: item[1], reverse=True)
    top_positive = [name for name, value in sorted_items if value > 0][:2]
    top_negative = [name for name, value in sorted(contributions.items(), key=lambda item: item[1]) if value < 0][:2]
    missing_count = int(row.get("missing_count", 0)) if pd.notna(row.get("missing_count", 0)) else 0
    composite = row.get("composite_score")
    explanation = (
        f"Composite score {composite:.4f}. "
        f"Positive drivers: {', '.join(top_positive) if top_positive else 'none'}. "
        f"Negative drivers: {', '.join(top_negative) if top_negative else 'none'}. "
        f"Missing factor fields: {missing_count}."
    )
    return {
        "composite_score": row.get("composite_score"),
        "momentum_score": row.get("momentum_score"),
        "value_score": row.get("value_score"),
        "quality_score": row.get("quality_score"),
        "low_vol_score": row.get("low_vol_score"),
        "factor_contributions": contributions,
        "top_positive_factors": top_positive,
        "top_negative_factors": top_negative,
        "missing_count": missing_count,
        "explanation": explanation,
    }


def attach_explanations(decisions: pd.DataFrame, factor_scores: pd.DataFrame, factor_weights: dict[str, float]) -> pd.DataFrame:
    if decisions.empty:
        return decisions
    scores = factor_scores.copy().reset_index(drop=True)
    score_by_ticker = scores.drop_duplicates("ticker").set_index("ticker", drop=False)
    rows = []
    for _, decision in decisions.iterrows():
        row = decision.to_dict()
        ticker = row["ticker"]
        if ticker in score_by_ticker.index:
            explanation = build_factor_explanation(score_by_ticker.loc[ticker], factor_weights)
        else:
            explanation = {
                "composite_score": pd.NA,
                "momentum_score": pd.NA,
                "value_score": pd.NA,
                "quality_score": pd.NA,
                "low_vol_score": pd.NA,
                "factor_contributions": {},
                "top_positive_factors": [],
                "top_negative_factors": [],
                "missing_count": pd.NA,
                "explanation": "No factor score row available for this ticker.",
            }
        row.update(explanation)
        row["factor_contributions"] = json.dumps(row["factor_contributions"], sort_keys=True)
        row["top_positive_factors"] = json.dumps(row["top_positive_factors"])
        row["top_negative_factors"] = json.dumps(row["top_negative_factors"])
        rows.append(row)
    return pd.DataFrame(rows)
