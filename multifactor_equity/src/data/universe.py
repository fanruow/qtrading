from __future__ import annotations

import pandas as pd

from src.data.fundamental_loader import fundamentals_asof


def build_eligible_universe(
    as_of: pd.Timestamp,
    close: pd.DataFrame,
    volume: pd.DataFrame,
    fundamentals: pd.DataFrame,
    config: dict,
) -> pd.DataFrame:
    as_of = pd.Timestamp(as_of)
    if as_of not in close.index:
        raise ValueError(f"{as_of.date()} not in price index")
    f = fundamentals_asof(fundamentals, as_of)
    if f.empty:
        return pd.DataFrame()
    prices = close.loc[:as_of]
    vols = volume.loc[:as_of]
    tickers = [t for t in f.index if t in close.columns]
    rows = []
    for ticker in tickers:
        s = prices[ticker].dropna()
        if len(s) < config["min_history_days"] or s.index.max() != as_of:
            continue
        price = s.loc[as_of]
        adv20 = (prices[ticker] * vols[ticker]).loc[:as_of].dropna().tail(20).mean()
        meta = f.loc[ticker]
        checks = [
            meta["security_type"] == config["allowed_security_type"],
            not bool(meta["is_adr"]),
            not bool(meta["is_etf"]),
            not bool(meta["is_otc"]),
            not bool(meta["is_preferred"]),
            price > config["min_price"],
            adv20 > config["min_avg_dollar_volume_20d"],
            meta["market_cap"] > config["min_market_cap"],
            meta["available_date"] <= as_of,
        ]
        if all(checks):
            row = meta.to_dict()
            row["price"] = price
            row["avg_dollar_volume_20d"] = adv20
            rows.append(row)
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).set_index("ticker", drop=False)
