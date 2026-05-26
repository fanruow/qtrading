from __future__ import annotations

from datetime import datetime, timezone

import pytest

from quant_options_monitor.features.regime import MarketRegime, RegimeResult
from quant_options_monitor.options.mock_provider import MockOptionsProvider
from quant_options_monitor.options.models import OptionChain
from quant_options_monitor.options.selector import OptionsStrategySelectorSettings
from quant_options_monitor.options.strategies.butterfly import LongButterflySelector


def chain() -> OptionChain:
    return MockOptionsProvider(
        underlying_prices={"SPY": 500.0},
        as_of=datetime(2026, 5, 26, tzinfo=timezone.utc),
    ).get_chain("SPY")


def range_regime(score: float = 0.9) -> RegimeResult:
    return RegimeResult(
        symbol="SPY",
        regime=MarketRegime.RANGE_BOUND,
        trend_score=0.0,
        range_score=score,
        volatility_score=0.0,
        reasons=["Range-bound test regime."],
    )


def test_long_butterfly_creates_one_short_two_one_call_structure() -> None:
    option_chain = chain()

    candidate = LongButterflySelector().select(
        symbol="SPY",
        underlying_price=option_chain.underlying_price,
        option_chain=option_chain,
        regime_result=range_regime(),
        settings=OptionsStrategySelectorSettings(),
    )

    assert candidate is not None
    assert candidate.strategy_name == "long_butterfly"
    assert [leg.action for leg in candidate.legs] == ["buy", "sell", "buy"]
    assert [leg.quantity for leg in candidate.legs] == [1, 2, 1]
    lower, middle, upper = [leg.option for leg in candidate.legs]
    assert lower.option_type == middle.option_type == upper.option_type == "call"
    assert lower.strike < middle.strike < upper.strike
    assert middle.strike - lower.strike == pytest.approx(upper.strike - middle.strike)
    assert 7 <= (middle.expiration - option_chain.as_of.date()).days <= 45

    debit = lower.ask - 2 * middle.bid + upper.ask
    expected_max_loss = round(max(debit, 0.01) * 100, 2)
    expected_max_profit = round((middle.strike - lower.strike) * 100 - expected_max_loss, 2)

    assert candidate.max_loss == pytest.approx(expected_max_loss)
    assert candidate.max_profit == pytest.approx(expected_max_profit)
    assert candidate.breakevens == [
        pytest.approx(round(lower.strike + expected_max_loss / 100, 2)),
        pytest.approx(round(upper.strike - expected_max_loss / 100, 2)),
    ]
    assert candidate.estimated_debit_or_credit == pytest.approx(-expected_max_loss)


def test_long_butterfly_rejects_if_symmetric_wings_unavailable() -> None:
    option_chain = chain()
    contracts = [
        contract
        for contract in option_chain.contracts
        if not (
            contract.option_type == "call"
            and 7 <= (contract.expiration - option_chain.as_of.date()).days <= 45
            and contract.strike < 500.0
        )
    ]
    broken_chain = option_chain.model_copy(update={"contracts": contracts})

    candidate = LongButterflySelector().select(
        symbol="SPY",
        underlying_price=broken_chain.underlying_price,
        option_chain=broken_chain,
        regime_result=range_regime(),
        settings=OptionsStrategySelectorSettings(),
    )

    assert candidate is None


def test_long_butterfly_rejects_low_range_score() -> None:
    option_chain = chain()

    candidate = LongButterflySelector().select(
        symbol="SPY",
        underlying_price=option_chain.underlying_price,
        option_chain=option_chain,
        regime_result=range_regime(score=0.2),
        settings=OptionsStrategySelectorSettings(),
    )

    assert candidate is None
