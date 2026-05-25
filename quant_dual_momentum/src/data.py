"""Data download and preparation helpers."""

from __future__ import annotations

import pandas as pd
import yfinance as yf


def download_adjusted_close(
    tickers: list[str],
    start: str,
    end: str | None = None,
    auto_adjust: bool = True,
) -> pd.DataFrame:
    """Download adjusted close prices from Yahoo Finance.

    Missing prices are left as missing. In particular, this function does not
    forward-fill dates before an ETF existed.
    """
    raw = yf.download(
        tickers=tickers,
        start=start,
        end=end,
        auto_adjust=auto_adjust,
        progress=False,
        group_by="column",
        threads=False,
    )
    if raw.empty:
        raise ValueError("No price data downloaded.")

    if auto_adjust:
        if isinstance(raw.columns, pd.MultiIndex):
            prices = raw["Close"].copy()
        else:
            prices = raw[["Close"]].copy()
            prices.columns = tickers
    else:
        if isinstance(raw.columns, pd.MultiIndex):
            prices = raw["Adj Close"].copy()
        else:
            prices = raw[["Adj Close"]].copy()
            prices.columns = tickers

    prices = prices.reindex(columns=tickers)
    prices.index = pd.to_datetime(prices.index)
    prices = prices.sort_index()
    prices = prices.dropna(how="all")
    missing_tickers = prices.columns[prices.isna().all()].tolist()
    if missing_tickers:
        raise ValueError(f"No price data downloaded for: {', '.join(missing_tickers)}")
    return prices


def compute_daily_returns(prices: pd.DataFrame) -> pd.DataFrame:
    """Compute daily close-to-close returns without filling missing prices."""
    return prices.pct_change(fill_method=None)
