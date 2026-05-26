from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from quant_options_monitor.options.models import (
    OptionChain,
    OptionContract,
    OptionLeg,
    OptionStrategyCandidate,
)


def contract(days_to_expiration: int = 30) -> OptionContract:
    return OptionContract(
        symbol="spy260619c00500000",
        underlying_symbol="spy",
        expiration=datetime.now(timezone.utc).date() + timedelta(days=days_to_expiration),
        strike=500.0,
        option_type="call",
        bid=4.0,
        ask=4.4,
        last=4.1,
        volume=1000,
        open_interest=5000,
        implied_volatility=0.22,
        delta=0.45,
        gamma=0.02,
        theta=-0.04,
        vega=0.12,
    )


def test_option_contract_helper_properties() -> None:
    option = contract(days_to_expiration=45)

    assert option.symbol == "SPY260619C00500000"
    assert option.underlying_symbol == "SPY"
    assert option.mid_price == pytest.approx(4.2)
    assert option.bid_ask_spread == pytest.approx(0.4)
    assert option.bid_ask_spread_pct == pytest.approx(0.4 / 4.2)
    assert option.dte == 45


def test_option_contract_uses_last_as_mid_when_quote_is_missing() -> None:
    option = contract()
    option = option.model_copy(update={"bid": 0.0, "ask": 0.0, "last": 3.7})

    assert option.mid_price == 3.7
    assert option.bid_ask_spread_pct == 0.0


def test_option_chain_and_strategy_dump_are_alert_ready() -> None:
    option = contract()
    chain = OptionChain(
        underlying_symbol="spy",
        underlying_price=502.25,
        as_of=datetime(2026, 5, 26, 14, 30, tzinfo=timezone.utc),
        contracts=[option],
    )
    candidate = OptionStrategyCandidate(
        strategy_name="bull_call_spread",
        underlying_symbol="SPY",
        legs=[OptionLeg(action="buy", option=option, quantity=1)],
        max_loss=420.0,
        max_profit=580.0,
        breakevens=[504.2],
        estimated_debit_or_credit=-420.0,
        score=0.78,
        reasons=["Bullish trend and liquid option chain."],
        warnings=[],
    )

    output = candidate.as_alert_dict()

    assert chain.contracts[0].mid_price == pytest.approx(4.2)
    assert output["strategy_name"] == "bull_call_spread"
    assert output["legs"][0]["option"]["mid_price"] == pytest.approx(4.2)
    assert output["legs"][0]["estimated_premium"] == pytest.approx(-420.0)
    assert output["reasons"] == ["Bullish trend and liquid option chain."]


def test_option_models_validate_invalid_values() -> None:
    with pytest.raises(ValidationError):
        OptionContract(
            symbol="SPY",
            underlying_symbol="SPY",
            expiration=datetime.now(timezone.utc).date(),
            strike=-1.0,
            option_type="call",
        )

    with pytest.raises(ValidationError):
        OptionLeg(action="buy", option=contract(), quantity=0)
