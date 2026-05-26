from __future__ import annotations

from datetime import datetime, timezone

import pytest

from quant_options_monitor.features.regime import MarketRegime, RegimeResult
from quant_options_monitor.options.mock_provider import MockOptionsProvider
from quant_options_monitor.options.selector import OptionsStrategySelectorSettings
from quant_options_monitor.options.strategies.put_spread import BearPutSpreadSelector


def chain():
    return MockOptionsProvider(
        underlying_prices={"SPY": 500.0},
        as_of=datetime(2026, 5, 26, tzinfo=timezone.utc),
    ).get_chain("SPY")


def regime(regime_value: MarketRegime, trend_score: float) -> RegimeResult:
    return RegimeResult(
        symbol="SPY",
        regime=regime_value,
        trend_score=trend_score,
        range_score=0.0,
        volatility_score=0.0,
        reasons=[f"{regime_value.value} test regime."],
    )


def test_bear_put_spread_generates_candidate_in_bearish_condition() -> None:
    option_chain = chain()

    candidate = BearPutSpreadSelector().select(
        symbol="SPY",
        underlying_price=option_chain.underlying_price,
        option_chain=option_chain,
        regime_result=regime(MarketRegime.BEARISH_TREND, trend_score=-0.9),
        settings=OptionsStrategySelectorSettings(),
    )

    assert candidate is not None
    assert candidate.strategy_name == "bear_put_spread"
    assert len(candidate.legs) == 2
    long_leg, short_leg = candidate.legs
    assert long_leg.action == "buy"
    assert short_leg.action == "sell"
    assert long_leg.option.option_type == "put"
    assert short_leg.option.option_type == "put"
    assert 30 <= (long_leg.option.expiration - option_chain.as_of.date()).days <= 60
    assert -0.60 <= float(long_leg.option.delta or 0) <= -0.45
    assert -0.35 <= float(short_leg.option.delta or 0) <= -0.20
    assert short_leg.option.strike < long_leg.option.strike
    assert candidate.score > 0
    assert candidate.reasons


def test_bear_put_spread_returns_no_candidate_in_bullish_condition() -> None:
    option_chain = chain()

    candidate = BearPutSpreadSelector().select(
        symbol="SPY",
        underlying_price=option_chain.underlying_price,
        option_chain=option_chain,
        regime_result=regime(MarketRegime.BULLISH_TREND, trend_score=0.9),
        settings=OptionsStrategySelectorSettings(),
    )

    assert candidate is None


def test_bear_put_spread_calculates_max_loss_and_profit() -> None:
    option_chain = chain()

    candidate = BearPutSpreadSelector().select(
        symbol="SPY",
        underlying_price=option_chain.underlying_price,
        option_chain=option_chain,
        regime_result=regime(MarketRegime.BEARISH_TREND, trend_score=-0.9),
        settings=OptionsStrategySelectorSettings(),
    )

    assert candidate is not None
    long_put = candidate.legs[0].option
    short_put = candidate.legs[1].option
    debit = long_put.ask - short_put.bid
    expected_max_loss = round(debit * 100, 2)
    expected_max_profit = round((long_put.strike - short_put.strike) * 100 - expected_max_loss, 2)

    assert candidate.max_loss == pytest.approx(expected_max_loss)
    assert candidate.max_profit == pytest.approx(expected_max_profit)
    assert candidate.breakevens == [pytest.approx(round(long_put.strike - debit, 2))]
    assert candidate.estimated_debit_or_credit == pytest.approx(-expected_max_loss)
