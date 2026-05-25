"""Alpaca paper trading broker adapter."""

from __future__ import annotations

import os

from dotenv import load_dotenv

from .broker_base import AccountSnapshot, BrokerBase, PlannedOrder, Position


class AlpacaBroker(BrokerBase):
    """Broker adapter restricted to Alpaca paper trading by default."""

    def __init__(self, api_key: str | None = None, secret_key: str | None = None, paper: bool = True) -> None:
        """Create an Alpaca TradingClient for paper trading.

        Passing paper=False raises immediately to avoid accidental live trading.
        """
        if not paper:
            raise ValueError("Live trading is disabled. Set paper=True to use Alpaca paper trading.")

        load_dotenv()
        self.api_key = api_key or os.getenv("ALPACA_API_KEY")
        self.secret_key = secret_key or os.getenv("ALPACA_SECRET_KEY")
        if not self.api_key or not self.secret_key:
            raise ValueError("Missing Alpaca credentials. Set ALPACA_API_KEY and ALPACA_SECRET_KEY in .env.")

        try:
            from alpaca.trading.client import TradingClient
        except ImportError as exc:
            raise ImportError("alpaca-py is required for AlpacaBroker. Install requirements.txt.") from exc

        self.client = TradingClient(self.api_key, self.secret_key, paper=True)

    def get_account(self) -> AccountSnapshot:
        """Return current Alpaca account equity and cash."""
        account = self.client.get_account()
        return AccountSnapshot(equity=float(account.equity), cash=float(account.cash))

    def get_positions(self) -> dict[str, Position]:
        """Return current Alpaca positions keyed by symbol."""
        positions = {}
        for item in self.client.get_all_positions():
            positions[item.symbol] = Position(
                symbol=item.symbol,
                qty=float(item.qty),
                market_value=float(item.market_value),
            )
        return positions

    def submit_order(self, order: PlannedOrder) -> object:
        """Submit a market day order to Alpaca paper trading."""
        from alpaca.trading.enums import OrderSide, TimeInForce
        from alpaca.trading.requests import MarketOrderRequest

        request = MarketOrderRequest(
            symbol=order.symbol,
            qty=order.qty,
            side=OrderSide.BUY if order.side == "buy" else OrderSide.SELL,
            time_in_force=TimeInForce.DAY,
        )
        return self.client.submit_order(order_data=request)
