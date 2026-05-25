from __future__ import annotations

import json

import pandas as pd

from src.decisions.decision_engine import build_current_vs_target
from src.decisions.explanations import attach_explanations, factor_contributions
from src.decisions.order_preview import generate_order_preview


def sample_factor_scores() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "signal_date": [pd.Timestamp("2021-01-29")] * 6,
            "ticker": ["BUY", "SELL", "ADD", "TRIM", "HOLD", "SKIP"],
            "sector": ["Tech"] * 6,
            "composite_score": [6.0, 1.0, 5.0, 4.0, 3.0, 2.0],
            "momentum_score": [1.0, -1.0, 0.5, -0.5, 0.1, 2.0],
            "value_score": [0.5, -0.5, 0.2, -0.2, 0.0, 1.0],
            "quality_score": [0.2, -0.2, 0.1, -0.1, 0.0, 0.5],
            "low_vol_score": [0.1, -0.1, 0.0, 0.2, 0.0, -0.5],
            "missing_count": [0, 1, 0, 0, 0, 2],
        }
    )


def sample_current_positions() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "ticker": ["SELL", "ADD", "TRIM", "HOLD"],
            "current_weight": [0.03, 0.01, 0.05, 0.020],
            "current_shares": [10, 4, 20, 8],
        }
    )


def test_decision_engine_buy_sell_add_trim_hold_and_skip():
    target_weights = pd.Series({"BUY": 0.02, "ADD": 0.02, "TRIM": 0.03, "HOLD": 0.021})

    decisions = build_current_vs_target(sample_current_positions(), target_weights, sample_factor_scores(), top_n=6, min_weight_change=0.0025)
    by_ticker = decisions.set_index("ticker")["decision"].to_dict()

    assert by_ticker["BUY"] == "BUY"
    assert by_ticker["SELL"] == "SELL"
    assert by_ticker["ADD"] == "ADD"
    assert by_ticker["TRIM"] == "TRIM"
    assert by_ticker["HOLD"] == "HOLD"
    assert by_ticker["SKIP"] == "SKIP"


def test_min_weight_change_threshold_is_respected():
    current = pd.DataFrame({"ticker": ["AAA"], "current_weight": [0.02], "current_shares": [1]})
    target = pd.Series({"AAA": 0.0224})
    scores = pd.DataFrame({"ticker": ["AAA"], "composite_score": [1.0]})

    decisions = build_current_vs_target(current, target, scores, top_n=1, min_weight_change=0.0025)

    assert decisions.loc[0, "decision"] == "HOLD"


def test_factor_contribution_is_weighted_score_from_existing_fields():
    row = pd.Series({"momentum_score": 2.0, "value_score": -1.0, "quality_score": 0.5, "low_vol_score": 0.0})
    weights = {"momentum_score": 0.30, "value_score": 0.25, "quality_score": 0.25, "low_vol_score": 0.20}

    contributions = factor_contributions(row, weights)

    assert contributions["momentum_score"] == 0.60
    assert contributions["value_score"] == -0.25
    assert contributions["quality_score"] == 0.125
    assert contributions["low_vol_score"] == 0.0


def test_explanation_uses_existing_factor_scores():
    target_weights = pd.Series({"BUY": 0.02})
    decisions = build_current_vs_target(pd.DataFrame(columns=["ticker", "current_weight", "current_shares"]), target_weights, sample_factor_scores(), top_n=1, min_weight_change=0.0025)
    weights = {"momentum_score": 0.30, "value_score": 0.25, "quality_score": 0.25, "low_vol_score": 0.20}

    explained = attach_explanations(decisions, sample_factor_scores(), weights)
    row = explained.set_index("ticker").loc["BUY"]
    contributions = json.loads(row["factor_contributions"])

    assert row["composite_score"] == 6.0
    assert row["momentum_score"] == 1.0
    assert contributions["momentum_score"] == 0.30
    assert "Composite score 6.0000" in row["explanation"]


def test_orders_preview_only_generates_preview_without_broker():
    decisions = pd.DataFrame(
        {
            "ticker": ["BUY", "TRIM", "HOLD"],
            "decision": ["BUY", "TRIM", "HOLD"],
            "current_weight": [0.0, 0.05, 0.02],
            "target_weight": [0.02, 0.03, 0.021],
            "explanation": ["buy reason", "trim reason", "hold reason"],
        }
    )
    latest_prices = pd.Series({"BUY": 10.0, "TRIM": 20.0, "HOLD": 30.0})

    preview = generate_order_preview(decisions, latest_prices, portfolio_value=100_000, min_trade_notional=100, allow_fractional_shares=False)

    assert set(preview["ticker"]) == {"BUY", "TRIM"}
    assert "side" in preview.columns
    assert "share_delta" in preview.columns
    assert "estimated_notional" in preview.columns
    assert "reason_summary" in preview.columns
