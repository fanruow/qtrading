"""Synthetic options provider for tests and local development."""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta, timezone

from quant_options_monitor.options.models import OptionChain, OptionContract, OptionType
from quant_options_monitor.options.provider_base import BaseOptionsProvider


class MockOptionsProvider(BaseOptionsProvider):
    """Generate deterministic, liquid synthetic option chains."""

    dte_buckets = (7, 14, 30, 45, 60, 90)

    def __init__(
        self,
        underlying_prices: dict[str, float] | None = None,
        as_of: datetime | None = None,
        strike_step: float = 5.0,
        strike_span_pct: float = 0.20,
    ) -> None:
        self.underlying_prices = {key.upper(): value for key, value in (underlying_prices or {}).items()}
        self.as_of = as_of or datetime.now(timezone.utc)
        self.strike_step = strike_step
        self.strike_span_pct = strike_span_pct

    def get_chain(self, symbol: str) -> OptionChain:
        normalized_symbol = symbol.strip().upper()
        underlying_price = self._underlying_price(normalized_symbol)
        contracts: list[OptionContract] = []
        for expiration in self.get_expirations(normalized_symbol):
            dte = max((expiration - self.as_of.date()).days, 1)
            for strike in self._strikes_around(underlying_price):
                contracts.append(
                    self._contract(
                        underlying_symbol=normalized_symbol,
                        underlying_price=underlying_price,
                        expiration=expiration,
                        strike=strike,
                        option_type=OptionType.CALL,
                        dte=dte,
                    )
                )
                contracts.append(
                    self._contract(
                        underlying_symbol=normalized_symbol,
                        underlying_price=underlying_price,
                        expiration=expiration,
                        strike=strike,
                        option_type=OptionType.PUT,
                        dte=dte,
                    )
                )
        return OptionChain(
            underlying_symbol=normalized_symbol,
            underlying_price=underlying_price,
            as_of=self.as_of,
            contracts=contracts,
        )

    def get_expirations(self, symbol: str) -> list[date]:
        return [self.as_of.date() + timedelta(days=dte) for dte in self.dte_buckets]

    def _underlying_price(self, symbol: str) -> float:
        if symbol in self.underlying_prices:
            return self.underlying_prices[symbol]
        seed = sum(ord(char) for char in symbol)
        return round(80.0 + seed % 220, 2)

    def _strikes_around(self, underlying_price: float) -> list[float]:
        lower = underlying_price * (1 - self.strike_span_pct)
        upper = underlying_price * (1 + self.strike_span_pct)
        first = math.floor(lower / self.strike_step) * self.strike_step
        last = math.ceil(upper / self.strike_step) * self.strike_step
        count = int(round((last - first) / self.strike_step)) + 1
        return [round(first + index * self.strike_step, 2) for index in range(count)]

    def _contract(
        self,
        *,
        underlying_symbol: str,
        underlying_price: float,
        expiration: date,
        strike: float,
        option_type: OptionType,
        dte: int,
    ) -> OptionContract:
        moneyness = (underlying_price - strike) / underlying_price
        time_value = underlying_price * (0.015 + math.sqrt(dte / 365) * 0.08)
        distance_discount = max(0.15, 1 - abs(moneyness) * 3.0)
        intrinsic = (
            max(underlying_price - strike, 0.0)
            if option_type == OptionType.CALL
            else max(strike - underlying_price, 0.0)
        )
        mid = max(intrinsic + time_value * distance_discount, 0.05)
        spread = max(0.02, mid * 0.04)
        bid = max(mid - spread / 2, 0.01)
        ask = mid + spread / 2
        iv = 0.18 + 0.08 * abs(moneyness) + 0.02 * math.sqrt(dte / 365)
        call_delta = min(max(0.5 + moneyness * 2.5, 0.05), 0.95)
        delta = call_delta if option_type == OptionType.CALL else call_delta - 1.0
        liquidity_decay = max(0.2, 1 - abs(moneyness) * 2.0)
        volume = int(100 + 1_500 * liquidity_decay + dte * 2)
        open_interest = int(500 + 6_000 * liquidity_decay + dte * 5)
        suffix = "C" if option_type == OptionType.CALL else "P"
        contract_symbol = (
            f"{underlying_symbol}{expiration.strftime('%y%m%d')}{suffix}"
            f"{int(round(strike * 1000)):08d}"
        )

        return OptionContract(
            symbol=contract_symbol,
            underlying_symbol=underlying_symbol,
            expiration=expiration,
            strike=strike,
            option_type=option_type,
            bid=round(bid, 2),
            ask=round(ask, 2),
            last=round(mid, 2),
            volume=volume,
            open_interest=open_interest,
            implied_volatility=round(iv, 4),
            delta=round(delta, 4),
            gamma=round(0.02 * liquidity_decay, 4),
            theta=round(-0.01 * mid / max(math.sqrt(dte), 1), 4),
            vega=round(0.08 * math.sqrt(dte / 365) * liquidity_decay, 4),
        )
