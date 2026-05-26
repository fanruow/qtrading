from __future__ import annotations

from datetime import datetime, timezone

from quant_options_monitor.options.mock_provider import MockOptionsProvider
from quant_options_monitor.options.models import OptionChain
from quant_options_monitor.options.provider_base import BaseOptionsProvider


def test_mock_provider_generates_spy_chain_with_expected_expirations() -> None:
    provider: BaseOptionsProvider = MockOptionsProvider(
        underlying_prices={"SPY": 500.0},
        as_of=datetime(2026, 5, 26, tzinfo=timezone.utc),
    )

    chain = provider.get_chain("SPY")
    expirations = provider.get_expirations("SPY")

    assert isinstance(chain, OptionChain)
    assert chain.underlying_symbol == "SPY"
    assert chain.underlying_price == 500.0
    assert len(expirations) == 6
    assert [(expiration - chain.as_of.date()).days for expiration in expirations] == [7, 14, 30, 45, 60, 90]


def test_mock_chain_contains_calls_puts_and_strikes_around_underlying() -> None:
    provider = MockOptionsProvider(
        underlying_prices={"SPY": 500.0},
        as_of=datetime(2026, 5, 26, tzinfo=timezone.utc),
    )

    chain = provider.get_chain("SPY")
    calls = [contract for contract in chain.contracts if contract.option_type == "call"]
    puts = [contract for contract in chain.contracts if contract.option_type == "put"]
    strikes = sorted({contract.strike for contract in chain.contracts})

    assert calls
    assert puts
    assert min(strikes) < 500.0
    assert max(strikes) > 500.0
    assert 500.0 in strikes
    assert len(chain.contracts) >= 6 * 2 * 15


def test_mock_chain_has_strategy_selector_ready_contract_data() -> None:
    provider = MockOptionsProvider(
        underlying_prices={"SPY": 500.0},
        as_of=datetime(2026, 5, 26, tzinfo=timezone.utc),
    )

    chain = provider.get_chain("SPY")
    contracts_30_dte = [contract for contract in chain.contracts if contract.dte == 30]
    near_money = [contract for contract in contracts_30_dte if abs(contract.strike - 500.0) <= 10]

    assert near_money
    assert all(contract.bid > 0 for contract in near_money)
    assert all(contract.ask > contract.bid for contract in near_money)
    assert all(contract.volume > 0 for contract in near_money)
    assert all(contract.open_interest > 0 for contract in near_money)
    assert all(contract.implied_volatility is not None for contract in near_money)
    assert any(contract.delta and contract.delta > 0 for contract in near_money)
    assert any(contract.delta and contract.delta < 0 for contract in near_money)
