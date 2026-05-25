from __future__ import annotations

import pandas as pd


def apply_long_only_constraints(
    selected: pd.DataFrame,
    max_stock_weight: float = 0.025,
    max_sector_weight: float = 0.25,
) -> pd.Series:
    if selected.empty:
        return pd.Series(dtype=float)
    weights = pd.Series(1.0 / len(selected), index=selected.index, dtype=float)
    weights = weights.clip(upper=max_stock_weight)
    sectors = selected["sector"]
    for _ in range(20):
        before = weights.copy()
        for sector, names in sectors.groupby(sectors).groups.items():
            sector_weight = weights.loc[list(names)].sum()
            if sector_weight > max_sector_weight:
                weights.loc[list(names)] *= max_sector_weight / sector_weight
        spare = min(1.0, len(weights) * max_stock_weight) - weights.sum()
        if spare <= 1e-12:
            break
        room = max_stock_weight - weights
        room = room.where(room > 1e-12, 0.0)
        sector_room = pd.Series(max_sector_weight, index=weights.index) - sectors.map(weights.groupby(sectors).sum())
        room = pd.concat([room, sector_room], axis=1).min(axis=1).clip(lower=0)
        if room.sum() <= 1e-12:
            break
        weights += spare * room / room.sum()
        if (weights - before).abs().sum() < 1e-10:
            break
    return weights.clip(lower=0)
