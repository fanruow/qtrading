from __future__ import annotations

import json
import os
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from src.paper_trading.broker import Account, BrokerInterface, OrderRequest, Position


class AlpacaPaperBroker(BrokerInterface):
    def __init__(
        self,
        api_key: str | None = None,
        secret_key: str | None = None,
        base_url: str | None = None,
    ):
        self.api_key = api_key or os.environ.get("ALPACA_API_KEY")
        self.secret_key = secret_key or os.environ.get("ALPACA_SECRET_KEY")
        self.base_url = (base_url or os.environ.get("ALPACA_PAPER_BASE_URL") or "").rstrip("/")
        if not self.api_key or not self.secret_key:
            raise ValueError("ALPACA_API_KEY and ALPACA_SECRET_KEY must be set for Alpaca paper trading")
        if not self.base_url:
            raise ValueError("ALPACA_PAPER_BASE_URL must be set for Alpaca paper trading")
        if "paper-api.alpaca.markets" not in self.base_url:
            raise ValueError("AlpacaPaperBroker only allows the Alpaca paper endpoint")

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None, query: dict[str, Any] | None = None) -> Any:
        url = f"{self.base_url}{path}"
        if query:
            url = f"{url}?{urlencode(query)}"
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        req = Request(
            url,
            data=body,
            method=method,
            headers={
                "APCA-API-KEY-ID": self.api_key,
                "APCA-API-SECRET-KEY": self.secret_key,
                "Content-Type": "application/json",
            },
        )
        try:
            with urlopen(req, timeout=20) as response:
                data = response.read().decode("utf-8")
                return json.loads(data) if data else {}
        except HTTPError as exc:
            detail = exc.read().decode("utf-8")
            raise RuntimeError(f"Alpaca paper API error {exc.code}: {detail}") from exc

    def get_account(self) -> Account:
        data = self._request("GET", "/v2/account")
        return Account(equity=float(data["equity"]), cash=float(data["cash"]))

    def get_positions(self) -> list[Position]:
        data = self._request("GET", "/v2/positions")
        return [Position(symbol=row["symbol"], market_value=float(row["market_value"])) for row in data]

    def get_tradable_symbols(self) -> set[str]:
        data = self._request("GET", "/v2/assets", query={"status": "active", "asset_class": "us_equity"})
        return {row["symbol"] for row in data if row.get("tradable") is True}

    def submit_order(self, order: OrderRequest) -> dict[str, Any]:
        payload = {
            "symbol": order.symbol,
            "side": order.side,
            "type": order.type,
            "time_in_force": order.time_in_force,
            "notional": round(float(order.notional), 2),
        }
        return self._request("POST", "/v2/orders", payload=payload)
