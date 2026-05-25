from __future__ import annotations

import pandas as pd

from src.reporting.explainability import build_decision_explanations


def test_explanation_values_are_consistent_with_factor_scores():
    signal_date = pd.Timestamp("2021-01-29")
    execution_date = pd.Timestamp("2021-02-01")
    factor_scores = pd.DataFrame(
        {
            "signal_date": [signal_date, signal_date],
            "ticker": ["AAA", "BBB"],
            "sector": ["Tech", "Tech"],
            "composite_score": [2.0, 1.0],
            "momentum_score": [1.5, 0.2],
            "value_score": [0.1, 0.3],
            "quality_score": [0.7, -0.1],
            "low_vol_score": [0.4, 0.0],
            "mom_12_1": [0.25, 0.05],
            "mom_12_1_winsor": [0.22, 0.05],
            "mom_12_1_sector_z": [1.0, -1.0],
            "fcf_yield": [pd.NA, 0.04],
            "fcf_yield_winsor": [pd.NA, 0.04],
            "fcf_yield_sector_z": [pd.NA, 0.0],
            "roe": [0.2, 0.1],
            "roe_winsor": [0.2, 0.1],
            "roe_sector_z": [1.0, -1.0],
            "gross_margin": [0.6, 0.4],
            "gross_margin_winsor": [0.6, 0.4],
            "gross_margin_sector_z": [1.0, -1.0],
            "neg_beta_252_sector_z": [0.8, -0.8],
            "momentum_missing_count": [0, 0],
            "value_missing_count": [1, 0],
            "quality_missing_count": [0, 0],
            "low_vol_missing_count": [0, 0],
            "missing_count": [1, 0],
        }
    )
    rebalance_log = pd.DataFrame({"signal_date": [signal_date], "execution_date": [execution_date]})
    positions = pd.DataFrame({"date": [execution_date], "ticker": ["AAA"], "weight": [0.025]})

    explanations = build_decision_explanations(factor_scores, rebalance_log, positions)

    assert len(explanations) == 1
    row = explanations.iloc[0]
    source = factor_scores.set_index("ticker").loc["AAA"]
    assert row["composite_score"] == source["composite_score"]
    assert row["momentum_score"] == source["momentum_score"]
    assert row["mom_12_1"] == source["mom_12_1"]
    assert row["mom_12_1_winsor"] == source["mom_12_1_winsor"]
    assert row["mom_12_1_sector_z"] == source["mom_12_1_sector_z"]
    assert row["missing_count"] == source["missing_count"]
    assert row["rank"] == 1
    assert "fcf_yield missing" in row["summary"]
