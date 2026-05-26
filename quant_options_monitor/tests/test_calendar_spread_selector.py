from __future__ import annotations

from datetime import datetime, timezone

import pytest

from quant_options_monitor.features.regime import MarketRegime, RegimeResult
from quant_options_monitor.options.mock_provider import MockOptionsProvider
from quant_options_monitor.options.models import OptionChain
from quant_options_monitor.options.selector import OptionsStrategySelectorSettings
from quant_options_monitor.options.strategies.calendar import CalendarSpreadSelector


def chain() -> OptionChain:
    return MockOptionsProvider(
        underlying_prices={"SPY": 500.0},
        as_of=datetime(2026, 5, 26, tzinfo=timezone.utc),
    ).get_chain("SPY")


def range_regime() -> RegimeResult:
    return RegimeResult(
        symbol="SPY",
        regime=MarketRegime.RANGE_BOUND,
        trend_score=0.0,
        range_score=0.9,
        volatility_score=0.0,
        reasons=["Range-bound test regime."],
    )


def favorable_term_structure(option_chain: OptionChain) -> OptionChain:
    contracts = []
    for contract in option_chain.contracts:
        dte = (contract.expiration - option_chain.as_of.date()).days
        if dte <= 30:
            contracts.append(contract.model_copy(update={"implied_volatility": 0.36}))
        else:
            contracts.append(contract.model_copy(update={"implied_volatility": 0.24}))
    return option_chain.model_copy(update={"contracts": contracts})


def test_calendar_spread_generates_call_and_put_candidates_when_front_iv_is_higher() -> None:
    option_chain = favorable_term_structure(chain())

    candidates = CalendarSpreadSelector().select(
        symbol="SPY",
        underlying_price=option_chain.underlying_price,
        option_chain=option_chain,
        regime_result=range_regime(),
        settings=OptionsStrategySelectorSettings(calendar_min_iv_spread=0.05),
    )

    assert {candidate.strategy_name for candidate in candidates} == {
        "call_calendar_spread",
        "put_calendar_spread",
    }
    for candidate in candidates:
        long_leg, short_leg = candidate.legs
        assert long_leg.action == "buy"
        assert short_leg.action == "sell"
        assert long_leg.option.option_type == short_leg.option.option_type
        assert long_leg.option.strike == short_leg.option.strike
        assert 7 <= (short_leg.option.expiration - option_chain.as_of.date()).days <= 30
        assert 30 <= (long_leg.option.expiration - option_chain.as_of.date()).days <= 90
        assert abs(long_leg.option.strike - option_chain.underlying_price) / option_chain.underlying_price <= 0.015
        assert candidate.max_loss == pytest.approx(
            round(max(long_leg.option.ask - short_leg.option.bid, 0.01) * 100, 2)
        )
        assert candidate.max_profit is None
        assert candidate.breakevens == []
        assert "Calendar max profit is path-dependent and approximate" in candidate.warnings
        assert (
            "Avoid holding short leg too close to expiration without active management"
            in candidate.warnings
        )


def test_calendar_spread_does_not_generate_when_term_structure_is_not_favorable() -> None:
    option_chain = chain()

    candidates = CalendarSpreadSelector().select(
        symbol="SPY",
        underlying_price=option_chain.underlying_price,
        option_chain=option_chain,
        regime_result=range_regime(),
        settings=OptionsStrategySelectorSettings(calendar_min_iv_spread=0.03),
    )

    assert candidates == []


def test_calendar_spread_requires_price_expected_near_target() -> None:
    option_chain = favorable_term_structure(chain())
    trending_regime = RegimeResult(
        symbol="SPY",
        regime=MarketRegime.BULLISH_TREND,
        trend_score=0.9,
        range_score=0.0,
        volatility_score=0.0,
        reasons=["Trending test regime."],
    )

    candidates = CalendarSpreadSelector().select(
        symbol="SPY",
        underlying_price=option_chain.underlying_price,
        option_chain=option_chain,
        regime_result=trending_regime,
        settings=OptionsStrategySelectorSettings(calendar_min_iv_spread=0.05),
    )

    assert candidates == []
