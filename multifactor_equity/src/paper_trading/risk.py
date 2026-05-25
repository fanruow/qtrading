from __future__ import annotations

import pandas as pd


def validate_paper_targets(
    target_weights: pd.Series,
    factor_scores: pd.DataFrame,
    known_symbols: set[str],
    max_stock_weight: float,
    max_sector_weight: float,
    cash_buffer: float,
) -> None:
    if (target_weights < -1e-12).any():
        raise ValueError("paper trading rejected: long-only target weights required")
    if target_weights.sum() > 1.0 - cash_buffer + 1e-12:
        raise ValueError("paper trading rejected: target weights exceed no-leverage cash-buffer limit")
    if target_weights.max() > max_stock_weight + 1e-12:
        raise ValueError("paper trading rejected: single-name weight exceeds max_stock_weight")
    unknown = sorted(set(target_weights.index) - set(known_symbols))
    if unknown:
        raise ValueError(f"paper trading rejected: unknown symbols {unknown}")
    score_rows = factor_scores.set_index("ticker", drop=False)
    missing_rows = sorted(set(target_weights.index) - set(score_rows.index))
    if missing_rows:
        raise ValueError(f"paper trading rejected: targets missing factor score rows {missing_rows}")
    sectors = score_rows.loc[target_weights.index, "sector"]
    sector_weights = target_weights.groupby(sectors).sum()
    if sector_weights.max() > max_sector_weight + 1e-12:
        raise ValueError("paper trading rejected: sector weight exceeds max_sector_weight")
