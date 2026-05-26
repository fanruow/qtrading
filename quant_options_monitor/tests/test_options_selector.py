from __future__ import annotations

from datetime import datetime, timezone

from quant_options_monitor.features.regime import MarketRegime, RegimeResult
from quant_options_monitor.options.mock_provider import MockOptionsProvider
from quant_options_monitor.options.models import LegAction, OptionStrategyCandidate
from quant_options_monitor.options.selector import (
    OptionsStrategySelector,
    OptionsStrategySelectorSettings,
)


def chain():
    return MockOptionsProvider(
        underlying_prices={"SPY": 500.0},
        as_of=datetime(2026, 5, 26, tzinfo=timezone.utc),
    ).get_chain("SPY")


def regime(regime_value: MarketRegime) -> RegimeResult:
    return RegimeResult(
        symbol="SPY",
        regime=regime_value,
        trend_score=1.0 if regime_value == MarketRegime.BULLISH_TREND else -1.0
        if regime_value == MarketRegime.BEARISH_TREND
        else 0.0,
        range_score=0.9 if regime_value == MarketRegime.RANGE_BOUND else 0.0,
        volatility_score=1.0 if regime_value == MarketRegime.HIGH_VOLATILITY else -1.0
        if regime_value == MarketRegime.LOW_VOLATILITY
        else 0.0,
        reasons=[f"{regime_value.value} test regime."],
    )


def test_selector_returns_sorted_bullish_candidates() -> None:
    candidates = OptionsStrategySelector().select(
        "SPY",
        chain(),
        regime(MarketRegime.BULLISH_TREND),
        OptionsStrategySelectorSettings(max_candidates_per_symbol=3),
    )

    assert candidates
    assert candidates[0].strategy_name == "bull_call_spread"
    assert _scores_descending(candidates)
    assert all(_has_no_naked_short(candidate) for candidate in candidates)
    assert all(candidate.max_loss is not None for candidate in candidates)
    assert all("Alert-only" in " ".join(candidate.warnings) for candidate in candidates)


def test_selector_returns_sorted_bearish_candidates() -> None:
    candidates = OptionsStrategySelector().select(
        "SPY",
        chain(),
        regime(MarketRegime.BEARISH_TREND),
        OptionsStrategySelectorSettings(max_candidates_per_symbol=3),
    )

    assert candidates
    assert candidates[0].strategy_name == "bear_put_spread"
    assert _scores_descending(candidates)
    assert all(_has_no_naked_short(candidate) for candidate in candidates)


def test_selector_combines_range_bound_strategies_and_caps_results() -> None:
    candidates = OptionsStrategySelector().select(
        "SPY",
        chain(),
        regime(MarketRegime.RANGE_BOUND),
        OptionsStrategySelectorSettings(max_candidates_per_symbol=1),
    )

    assert len(candidates) == 1
    assert candidates[0].strategy_name in {"long_butterfly", "iron_condor"}
    assert _scores_descending(candidates)
    assert _has_no_naked_short(candidates[0])


def test_selector_filters_illiquid_candidates() -> None:
    candidates = OptionsStrategySelector().select(
        "SPY",
        chain(),
        regime(MarketRegime.BULLISH_TREND),
        OptionsStrategySelectorSettings(
            min_option_volume=100_000,
            min_option_open_interest=100_000,
            max_candidates_per_symbol=3,
        ),
    )

    assert candidates == []


def _scores_descending(candidates: list[OptionStrategyCandidate]) -> bool:
    return [candidate.score for candidate in candidates] == sorted(
        [candidate.score for candidate in candidates], reverse=True
    )


def _has_no_naked_short(candidate: OptionStrategyCandidate) -> bool:
    for leg in candidate.legs:
        if leg.action != LegAction.SELL.value:
            continue
        short = leg.option
        protected = False
        for other in candidate.legs:
            option = other.option
            if other.action != LegAction.BUY.value:
                continue
            if option.option_type != short.option_type:
                continue
            if option.expiration == short.expiration and option.strike != short.strike:
                protected = True
            if option.expiration > short.expiration and option.strike == short.strike:
                protected = True
        if not protected:
            return False
    return True
