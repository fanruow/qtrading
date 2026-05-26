from __future__ import annotations

from datetime import datetime, timezone

import pytest

from quant_options_monitor.features.regime import MarketRegime, RegimeResult
from quant_options_monitor.options.mock_provider import MockOptionsProvider
from quant_options_monitor.options.models import OptionChain
from quant_options_monitor.options.selector import OptionsStrategySelectorSettings
from quant_options_monitor.options.strategies.iron_condor import IronCondorSelector


def chain() -> OptionChain:
    return MockOptionsProvider(
        underlying_prices={"SPY": 500.0},
        as_of=datetime(2026, 5, 26, tzinfo=timezone.utc),
    ).get_chain("SPY")


def condor_regime(
    trend_score: float = 0.0,
    range_score: float = 0.85,
    volatility_score: float = 0.8,
) -> RegimeResult:
    return RegimeResult(
        symbol="SPY",
        regime=MarketRegime.RANGE_BOUND,
        trend_score=trend_score,
        range_score=range_score,
        volatility_score=volatility_score,
        reasons=["Range-bound elevated-volatility test regime."],
    )


def test_iron_condor_creates_four_leg_defined_risk_candidate() -> None:
    option_chain = chain()

    candidate = IronCondorSelector().select(
        symbol="SPY",
        underlying_price=option_chain.underlying_price,
        option_chain=option_chain,
        regime_result=condor_regime(),
        settings=OptionsStrategySelectorSettings(),
    )

    assert candidate is not None
    assert candidate.strategy_name == "iron_condor"
    assert [leg.action for leg in candidate.legs] == ["sell", "buy", "sell", "buy"]
    assert [leg.quantity for leg in candidate.legs] == [1, 1, 1, 1]
    short_put, long_put, short_call, long_call = [leg.option for leg in candidate.legs]
    assert long_put.option_type == short_put.option_type == "put"
    assert short_call.option_type == long_call.option_type == "call"
    assert long_put.strike < short_put.strike < short_call.strike < long_call.strike
    assert 30 <= (short_put.expiration - option_chain.as_of.date()).days <= 45
    assert -0.25 <= float(short_put.delta or 0) <= -0.15
    assert 0.15 <= float(short_call.delta or 0) <= 0.25

    credit = short_put.bid + short_call.bid - long_put.ask - long_call.ask
    wing_width = min(short_put.strike - long_put.strike, long_call.strike - short_call.strike)
    assert candidate.max_profit == pytest.approx(round(credit * 100, 2))
    assert candidate.max_loss == pytest.approx(round(wing_width * 100 - credit * 100, 2))
    assert candidate.breakevens == [
        pytest.approx(round(short_put.strike - credit, 2)),
        pytest.approx(round(short_call.strike + credit, 2)),
    ]


def test_iron_condor_rejects_directional_regimes() -> None:
    option_chain = chain()

    candidate = IronCondorSelector().select(
        symbol="SPY",
        underlying_price=option_chain.underlying_price,
        option_chain=option_chain,
        regime_result=condor_regime(trend_score=0.7),
        settings=OptionsStrategySelectorSettings(),
    )

    assert candidate is None


def test_iron_condor_rejects_low_range_score() -> None:
    option_chain = chain()

    candidate = IronCondorSelector().select(
        symbol="SPY",
        underlying_price=option_chain.underlying_price,
        option_chain=option_chain,
        regime_result=condor_regime(range_score=0.3),
        settings=OptionsStrategySelectorSettings(),
    )

    assert candidate is None


def test_iron_condor_validates_liquidity() -> None:
    option_chain = chain()

    candidate = IronCondorSelector().select(
        symbol="SPY",
        underlying_price=option_chain.underlying_price,
        option_chain=option_chain,
        regime_result=condor_regime(),
        settings=OptionsStrategySelectorSettings(
            min_option_volume=100_000,
            min_option_open_interest=100_000,
        ),
    )

    assert candidate is None


def test_iron_condor_rejects_when_volatility_is_not_elevated() -> None:
    option_chain = chain()

    candidate = IronCondorSelector().select(
        symbol="SPY",
        underlying_price=option_chain.underlying_price,
        option_chain=option_chain,
        regime_result=condor_regime(volatility_score=0.1),
        settings=OptionsStrategySelectorSettings(),
    )

    assert candidate is None
