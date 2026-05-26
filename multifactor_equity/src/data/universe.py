from __future__ import annotations

import pandas as pd

from src.data.providers.base import FundamentalDataProvider, MetadataProvider


def _gt(value, threshold: float) -> bool:
    return bool(pd.notna(value) and float(value) > threshold)


def _lte_date(value, threshold: pd.Timestamp) -> bool:
    return bool(pd.notna(value) and pd.Timestamp(value) <= threshold)


def _is_false(value) -> bool:
    return bool(pd.notna(value) and not bool(value))


def fundamentals_asof(fundamentals: pd.DataFrame, as_of: pd.Timestamp) -> pd.DataFrame:
    eligible = fundamentals[fundamentals["available_date"] <= pd.Timestamp(as_of)].copy()
    eligible = eligible.sort_values(["ticker", "available_date", "report_date"])
    return eligible.groupby("ticker", as_index=False).tail(1).set_index("ticker", drop=False)


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
        if pd.isna(meta.get("market_cap", pd.NA)) and pd.notna(meta.get("shares_outstanding", pd.NA)):
            meta = meta.copy()
            meta["market_cap"] = float(price) * float(meta["shares_outstanding"])
        if pd.isna(meta.get("enterprise_value", pd.NA)) and pd.notna(meta.get("market_cap", pd.NA)):
            meta = meta.copy()
            debt = 0.0 if pd.isna(meta.get("total_debt", pd.NA)) else float(meta["total_debt"])
            meta["enterprise_value"] = float(meta["market_cap"]) + debt
        if pd.isna(meta.get("sector", pd.NA)):
            meta = meta.copy()
            meta["sector"] = "Unknown"
        checks = [
            bool(meta.get("security_type") == config["allowed_security_type"]),
            _is_false(meta.get("is_adr", False)),
            _is_false(meta.get("is_etf", False)),
            _is_false(meta.get("is_otc", False)),
            _is_false(meta.get("is_preferred", False)),
            _gt(price, config["min_price"]),
            _gt(adv20, config["min_avg_dollar_volume_20d"]),
            _gt(meta.get("market_cap", pd.NA), config["min_market_cap"]),
            _lte_date(meta.get("available_date", pd.NA), as_of),
        ]
        if all(checks):
            row = meta.to_dict()
            row["price"] = price
            row["avg_dollar_volume_20d"] = adv20
            rows.append(row)
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).set_index("ticker", drop=False)


def build_eligible_universe_from_providers(
    as_of: pd.Timestamp,
    close: pd.DataFrame,
    volume: pd.DataFrame,
    fundamental_provider: FundamentalDataProvider,
    metadata_provider: MetadataProvider,
    config: dict,
) -> pd.DataFrame:
    fundamentals = fundamental_provider.fundamentals_asof(as_of)
    metadata = metadata_provider.metadata_asof(as_of)
    if fundamentals.empty or metadata.empty:
        return pd.DataFrame()
    merged = fundamentals.drop(columns=[c for c in ["sector", "security_type", "is_adr", "is_etf", "is_otc", "is_preferred", "market_cap"] if c in fundamentals.columns])
    merged = metadata.join(merged, how="inner", rsuffix="_fundamental").reset_index(drop=True)
    return build_eligible_universe(as_of, close, volume, merged, config)
