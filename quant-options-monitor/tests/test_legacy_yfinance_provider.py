from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd

from src.data.providers import YFinanceMarketDataProvider


@dataclass
class FakeOptionChain:
    calls: pd.DataFrame
    puts: pd.DataFrame


class FakeTicker:
    def option_chain(self, expiration: str) -> FakeOptionChain:
        assert expiration == "2026-06-19"
        frame = pd.DataFrame(
            [
                {
                    "strike": 500.0,
                    "bid": float("nan"),
                    "ask": 5.1,
                    "lastPrice": float("nan"),
                    "volume": float("nan"),
                    "openInterest": float("nan"),
                    "impliedVolatility": float("nan"),
                }
            ]
        )
        return FakeOptionChain(calls=frame, puts=frame.copy())


class FakeYFinance:
    def Ticker(self, symbol: str) -> FakeTicker:
        assert symbol == "SPY"
        return FakeTicker()


def test_yfinance_option_chain_nan_values_are_cleaned() -> None:
    provider = YFinanceMarketDataProvider.__new__(YFinanceMarketDataProvider)
    provider._yf = FakeYFinance()

    contracts = provider.get_option_chain("SPY", date(2026, 6, 19))

    assert len(contracts) == 2
    assert contracts[0].bid == 0.0
    assert contracts[0].last == 0.0
    assert contracts[0].volume == 0
    assert contracts[0].open_interest == 0
    assert contracts[0].implied_volatility == 0.0
