from __future__ import annotations

import json
import os
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd

from src.data.providers.base import PriceData, PriceDataProvider


class AlpacaPriceProvider(PriceDataProvider):
    def __init__(
        self,
        api_key: str | None = None,
        secret_key: str | None = None,
        data_feed: str | None = None,
        base_url: str = "https://data.alpaca.markets",
        cache_enabled: bool = True,
    ):
        self.api_key = api_key or os.environ.get("ALPACA_API_KEY")
        self.secret_key = secret_key or os.environ.get("ALPACA_SECRET_KEY")
        self.data_feed = data_feed or os.environ.get("ALPACA_DATA_FEED", "iex")
        self.base_url = base_url.rstrip("/")
        self.cache_enabled = cache_enabled
        self._cache: dict[tuple[tuple[str, ...], str, str], PriceData] = {}
        if not self.api_key or not self.secret_key:
            raise ValueError("ALPACA_API_KEY and ALPACA_SECRET_KEY must be set for Alpaca price data")

    def _request_json(self, path: str, query: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}{path}?{urlencode(query)}"
        req = Request(
            url,
            method="GET",
            headers={
                "APCA-API-KEY-ID": self.api_key,
                "APCA-API-SECRET-KEY": self.secret_key,
            },
        )
        try:
            with urlopen(req, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8")
            raise RuntimeError(f"Alpaca data API error {exc.code}: {detail}") from exc

    def _download_bars(self, tickers: list[str], start: str, end: str) -> dict[str, Any]:
        query = {
            "symbols": ",".join(tickers),
            "timeframe": "1Day",
            "start": pd.Timestamp(start).date().isoformat(),
            "end": pd.Timestamp(end).date().isoformat(),
            "adjustment": "all",
            "feed": self.data_feed,
            "limit": 10000,
        }
        return self._request_json("/v2/stocks/bars", query)

    def load_prices(self, tickers: list[str], start: str, end: str) -> PriceData:
        key = (tuple(tickers), start, end)
        if self.cache_enabled and key in self._cache:
            return self._cache[key]
        payload = self._download_bars(tickers, start, end)
        data = self._parse_bars(payload, tickers)
        data.validate()
        if self.cache_enabled:
            self._cache[key] = data
        return data

    @staticmethod
    def _parse_bars(payload: dict[str, Any], tickers: list[str]) -> PriceData:
        bars = payload.get("bars", {})
        rows: list[dict[str, Any]] = []
        for ticker in tickers:
            for bar in bars.get(ticker, []):
                rows.append(
                    {
                        "date": pd.Timestamp(bar["t"]).tz_localize(None).normalize(),
                        "ticker": ticker,
                        "open": float(bar["o"]),
                        "high": float(bar["h"]),
                        "low": float(bar["l"]),
                        "close": float(bar["c"]),
                        "volume": float(bar["v"]),
                    }
                )
        if not rows:
            empty = pd.DataFrame(columns=tickers, dtype=float)
            return PriceData(open=empty.copy(), high=empty.copy(), low=empty.copy(), close=empty.copy(), volume=empty.copy())
        frame = pd.DataFrame(rows)
        fields = {}
        for field in ["open", "high", "low", "close", "volume"]:
            fields[field] = frame.pivot(index="date", columns="ticker", values=field).sort_index().reindex(columns=tickers)
        return PriceData(
            open=fields["open"],
            high=fields["high"],
            low=fields["low"],
            close=fields["close"],
            volume=fields["volume"],
        )
