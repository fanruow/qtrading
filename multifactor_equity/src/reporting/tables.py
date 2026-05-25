from __future__ import annotations

import pandas as pd


def to_csv(df: pd.DataFrame | pd.Series, path: str) -> None:
    if isinstance(df, pd.Series):
        df = df.to_frame().T
    df.to_csv(path, index=True)
