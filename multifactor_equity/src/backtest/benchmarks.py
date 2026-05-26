from __future__ import annotations

import pandas as pd


def buy_and_hold_returns(close: pd.DataFrame, ticker: str) -> pd.Series:
    return close[ticker].pct_change(fill_method=None).fillna(0.0)


def equal_weight_returns(close: pd.DataFrame, members_by_date: dict[pd.Timestamp, list[str]]) -> pd.Series:
    ret = close.pct_change(fill_method=None).fillna(0.0)
    out = pd.Series(0.0, index=close.index)
    current = []
    for date in close.index:
        if date in members_by_date:
            current = members_by_date[date]
        if current:
            out.loc[date] = ret.loc[date, current].mean()
    return out


def sector_neutral_equal_weight_returns(close: pd.DataFrame, sectors_by_ticker: dict[str, str], members_by_date: dict[pd.Timestamp, list[str]]) -> pd.Series:
    ret = close.pct_change(fill_method=None).fillna(0.0)
    out = pd.Series(0.0, index=close.index)
    current = []
    for date in close.index:
        if date in members_by_date:
            current = members_by_date[date]
        if current:
            groups: dict[str, list[str]] = {}
            for t in current:
                groups.setdefault(sectors_by_ticker.get(t, "Unknown"), []).append(t)
            out.loc[date] = pd.Series({s: ret.loc[date, names].mean() for s, names in groups.items()}).mean()
    return out
