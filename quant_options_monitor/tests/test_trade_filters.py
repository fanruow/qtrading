from __future__ import annotations

from datetime import datetime, timedelta, timezone

from quant_options_monitor.options.models import (
    OptionChain,
    OptionContract,
    OptionLeg,
    OptionStrategyCandidate,
)
from quant_options_monitor.risk.trade_filters import (
    TradeFilterSettings,
    filter_liquid_contracts,
    is_option_liquid,
    validate_strategy_liquidity,
)


def contract(
    *,
    symbol: str = "SPY260619C00500000",
    bid: float = 4.0,
    ask: float = 4.4,
    last: float = 4.2,
    volume: int = 1000,
    open_interest: int = 5000,
) -> OptionContract:
    return OptionContract(
        symbol=symbol,
        underlying_symbol="SPY",
        expiration=datetime.now(timezone.utc).date() + timedelta(days=30),
        strike=500.0,
        option_type="call",
        bid=bid,
        ask=ask,
        last=last,
        volume=volume,
        open_interest=open_interest,
        implied_volatility=0.22,
    )


def candidate_with(option: OptionContract) -> OptionStrategyCandidate:
    return OptionStrategyCandidate(
        strategy_name="bull_call_spread",
        underlying_symbol="SPY",
        legs=[OptionLeg(action="buy", option=option, quantity=1)],
        max_loss=420.0,
        max_profit=580.0,
        breakevens=[504.2],
        estimated_debit_or_credit=-420.0,
        score=0.75,
        reasons=["Test candidate."],
    )


def test_is_option_liquid_accepts_liquid_contract() -> None:
    assert is_option_liquid(contract(), min_volume=100, min_open_interest=500, max_spread_pct=0.15)


def test_is_option_liquid_rejects_bad_quotes_and_illiquid_contracts() -> None:
    settings = TradeFilterSettings(min_option_volume=100, min_option_open_interest=500, max_bid_ask_spread_pct=0.10)

    assert not is_option_liquid(
        contract(volume=99),
        settings.min_option_volume,
        settings.min_option_open_interest,
        settings.max_bid_ask_spread_pct,
    )
    assert not is_option_liquid(
        contract(open_interest=499),
        settings.min_option_volume,
        settings.min_option_open_interest,
        settings.max_bid_ask_spread_pct,
    )
    assert not is_option_liquid(
        contract(bid=0.0, ask=0.2, last=0.1),
        settings.min_option_volume,
        settings.min_option_open_interest,
        settings.max_bid_ask_spread_pct,
    )
    assert not is_option_liquid(
        contract(bid=1.0, ask=1.0, last=1.0),
        settings.min_option_volume,
        settings.min_option_open_interest,
        settings.max_bid_ask_spread_pct,
    )
    assert not is_option_liquid(
        contract(bid=1.0, ask=2.0, last=1.5),
        settings.min_option_volume,
        settings.min_option_open_interest,
        settings.max_bid_ask_spread_pct,
    )


def test_filter_liquid_contracts_returns_chain_copy_with_only_liquid_contracts() -> None:
    liquid = contract(symbol="SPY260619C00500000")
    low_volume = contract(symbol="SPY260619C00505000", volume=10)
    chain = OptionChain(
        underlying_symbol="SPY",
        underlying_price=500.0,
        as_of=datetime.now(timezone.utc),
        contracts=[liquid, low_volume],
    )

    filtered = filter_liquid_contracts(chain, TradeFilterSettings())

    assert filtered is not chain
    assert [option.symbol for option in filtered.contracts] == [liquid.symbol]
    assert len(chain.contracts) == 2


def test_validate_strategy_liquidity_rejects_illiquid_legs_with_warnings() -> None:
    option = contract(bid=0.0, ask=0.0, last=0.0, volume=10, open_interest=20)
    candidate = candidate_with(option)

    ok, warnings = validate_strategy_liquidity(candidate, TradeFilterSettings())

    assert not ok
    assert warnings
    assert candidate.warnings == warnings
    assert any("volume 10 below minimum 100" in warning for warning in warnings)
    assert any("open interest 20 below minimum 500" in warning for warning in warnings)
    assert any("bid must be greater than zero" in warning for warning in warnings)
    assert any("ask 0.00 must be greater than bid 0.00" in warning for warning in warnings)


def test_validate_strategy_liquidity_has_no_divide_by_zero_errors() -> None:
    option = contract(bid=0.0, ask=0.0, last=0.0)
    candidate = candidate_with(option)

    ok, warnings = validate_strategy_liquidity(
        candidate,
        {
            "min_option_volume": 1,
            "min_option_open_interest": 1,
            "max_bid_ask_spread_pct": 0.01,
        },
    )

    assert not ok
    assert warnings
