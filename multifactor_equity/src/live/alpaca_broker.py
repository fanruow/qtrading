from __future__ import annotations

import os
from typing import Any

from src.live.broker_interface import BrokerAccount, BrokerInterface, BrokerPosition, LiveOrder


class AlpacaPaperBroker(BrokerInterface):
    def __init__(self, api_key: str | None = None, secret_key: str | None = None, paper: bool = True):
        self.api_key = api_key or os.environ.get("ALPACA_API_KEY")
        self.secret_key = secret_key or os.environ.get("ALPACA_SECRET_KEY")
        self.paper = paper
        if not self.api_key or not self.secret_key:
            raise ValueError("ALPACA_API_KEY and ALPACA_SECRET_KEY must be set for Alpaca paper trading")
        if not self.paper:
            raise ValueError("AlpacaPaperBroker requires paper=True")
        try:
            from alpaca.trading.client import TradingClient
        except ImportError as exc:
            raise ImportError("alpaca-py is required for live_paper.py. Install package 'alpaca-py'.") from exc
        self.client = TradingClient(self.api_key, self.secret_key, paper=True)

    def assert_paper(self) -> None:
        if not self.paper:
            raise ValueError("Refusing to trade because broker is not confirmed paper environment")

    def is_market_open(self) -> bool:
        clock = self.client.get_clock()
        return bool(clock.is_open)

    def get_account(self) -> BrokerAccount:
        account = self.client.get_account()
        return BrokerAccount(equity=float(account.equity), cash=float(account.cash), buying_power=float(account.buying_power))

    def get_positions(self) -> list[BrokerPosition]:
        positions = self.client.get_all_positions()
        return [BrokerPosition(ticker=p.symbol, market_value=float(p.market_value), qty=float(p.qty)) for p in positions]

    def submit_order(self, order: LiveOrder) -> dict[str, Any]:
        self.assert_paper()
        from alpaca.trading.enums import OrderSide, TimeInForce
        from alpaca.trading.requests import MarketOrderRequest

        request = MarketOrderRequest(
            symbol=order.ticker,
            qty=order.qty,
            side=OrderSide.BUY if order.side == "buy" else OrderSide.SELL,
            time_in_force=TimeInForce.DAY,
            client_order_id=order.client_order_id,
        )
        submitted = self.client.submit_order(order_data=request)
        return {
            "id": str(getattr(submitted, "id", "")),
            "client_order_id": order.client_order_id,
            "ticker": order.ticker,
            "side": order.side,
            "qty": order.qty,
            "status": str(getattr(submitted, "status", "")),
        }
