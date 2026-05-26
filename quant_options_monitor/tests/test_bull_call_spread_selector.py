from __future__ import annotations

from datetime import datetime, timezone

import pytest

from quant_options_monitor.features.regime import MarketRegime, RegimeResult
from quant_options_monitor.options.mock_provider import MockOptionsProvider
from quant_options_monitor.options.selector import OptionsStrategySelectorSettings
from quant_options_monitor.options.strategies.call_spread import BullCallSpreadSelector


def chain():
    return MockOptionsProvider(
        underlying_prices={"SPY": 500.0},
        as_of=datetime(2026, 5, 26, tzinfo=timezone.utc),
    ).get_chain("SPY")


def regime(
    regime_value: MarketRegime,
    trend_score: float,
    volatility_score: float = 0.0,
) -> RegimeResult:
    return RegimeResult(
        symbol="SPY",
        regime=regime_value,
        trend_score=trend_score,
        range_score=0.0,
        volatility_score=volatility_score,
        reasons=[f"{regime_value.value} test regime."],
    )


def test_bull_call_spread_generates_candidate_in_bullish_condition() -> None:
    option_chain = chain()

    candidate = BullCallSpreadSelector().select(
        symbol="SPY",
        underlying_price=option_chain.underlying_price,
        option_chain=option_chain,
        regime_result=regime(MarketRegime.BULLISH_TREND, trend_score=0.9),
        settings=OptionsStrategySelectorSettings(),
    )

    assert candidate is not None
    assert candidate.strategy_name == "bull_call_spread"
    assert len(candidate.legs) == 2
    long_leg, short_leg = candidate.legs
    assert long_leg.action == "buy"
    assert short_leg.action == "sell"
    assert long_leg.option.option_type == "call"
    assert short_leg.option.option_type == "call"
    assert 30 <= (long_leg.option.expiration - option_chain.as_of.date()).days <= 60
    assert 0.45 <= float(long_leg.option.delta or 0) <= 0.60
    assert 0.20 <= float(short_leg.option.delta or 0) <= 0.35
    assert candidate.score > 0
    assert candidate.reasons


def test_bull_call_spread_returns_no_candidate_in_bearish_condition() -> None:
    option_chain = chain()

    candidate = BullCallSpreadSelector().select(
        symbol="SPY",
        underlying_price=option_chain.underlying_price,
        option_chain=option_chain,
        regime_result=regime(MarketRegime.BEARISH_TREND, trend_score=-0.9),
        settings=OptionsStrategySelectorSettings(),
    )

    assert candidate is None


def test_bull_call_spread_calculates_max_loss_and_profit() -> None:
    option_chain = chain()

    candidate = BullCallSpreadSelector().select(
        symbol="SPY",
        underlying_price=option_chain.underlying_price,
        option_chain=option_chain,
        regime_result=regime(MarketRegime.BULLISH_TREND, trend_score=0.9),
        settings=OptionsStrategySelectorSettings(),
    )

    assert candidate is not None
    long_call = candidate.legs[0].option
    short_call = candidate.legs[1].option
    debit = long_call.ask - short_call.bid
    expected_max_loss = round(debit * 100, 2)
    expected_max_profit = round((short_call.strike - long_call.strike) * 100 - expected_max_loss, 2)

    assert candidate.max_loss == pytest.approx(expected_max_loss)
    assert candidate.max_profit == pytest.approx(expected_max_profit)
    assert candidate.breakevens == [pytest.approx(round(long_call.strike + debit, 2))]
    assert candidate.estimated_debit_or_credit == pytest.approx(-expected_max_loss)
