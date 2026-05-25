from __future__ import annotations

import numpy as np
import pandas as pd


def winsorize_series(s: pd.Series, lower: float = 0.01, upper: float = 0.99) -> pd.Series:
    out = s.copy().astype(float)
    valid = out.dropna()
    if valid.empty:
        return out
    lo, hi = valid.quantile([lower, upper])
    return out.clip(lo, hi)


def zscore(s: pd.Series) -> pd.Series:
    s = s.astype(float)
    std = s.std(ddof=0)
    if pd.isna(std) or std == 0:
        return pd.Series(0.0, index=s.index).where(s.notna(), np.nan)
    return (s - s.mean()) / std


def sector_neutral_zscore(values: pd.Series, sectors: pd.Series) -> pd.Series:
    aligned = pd.DataFrame({"value": values, "sector": sectors})
    return aligned.groupby("sector", group_keys=False)["value"].apply(zscore)


def process_subfactors(
    df: pd.DataFrame,
    subfactors: list[str],
    sectors: pd.Series,
    lower: float = 0.01,
    upper: float = 0.99,
    max_missing: int = 2,
) -> tuple[pd.Series, pd.Series]:
    processed = pd.DataFrame(index=df.index)
    for col in subfactors:
        processed[col] = sector_neutral_zscore(winsorize_series(df[col], lower, upper), sectors)
    missing_count = df[subfactors].isna().sum(axis=1)
    score = processed.mean(axis=1, skipna=True)
    score = score.where(missing_count <= max_missing)
    return score, missing_count


def add_processed_subfactor_columns(
    df: pd.DataFrame,
    subfactors: list[str],
    sectors: pd.Series,
    lower: float = 0.01,
    upper: float = 0.99,
) -> pd.DataFrame:
    out = df.copy()
    for col in subfactors:
        winsor_col = f"{col}_winsor"
        z_col = f"{col}_sector_z"
        out[winsor_col] = winsorize_series(out[col], lower, upper)
        out[z_col] = sector_neutral_zscore(out[winsor_col], sectors)
    return out
