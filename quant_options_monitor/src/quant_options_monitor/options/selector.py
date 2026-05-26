"""Centralized options strategy selector for alert-only candidates."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Protocol

from quant_options_monitor.features.regime import MarketRegime, RegimeResult
from quant_options_monitor.options.models import (
    LegAction,
    OptionChain,
    OptionContract,
    OptionLeg,
    OptionStrategyCandidate,
)
from quant_options_monitor.options.strategies.calendar import CalendarSpreadSelector
from quant_options_monitor.options.strategies.call_spread import BullCallSpreadSelector
from quant_options_monitor.options.strategies.butterfly import LongButterflySelector
from quant_options_monitor.options.strategies.iron_condor import IronCondorSelector
from quant_options_monitor.options.strategies.put_spread import BearPutSpreadSelector
from quant_options_monitor.risk.trade_filters import (
    TradeFilterSettings,
    filter_liquid_contracts,
    validate_strategy_liquidity,
)


@dataclass(frozen=True)
class OptionsStrategySelectorSettings(TradeFilterSettings):
    max_candidates_per_symbol: int = 5
    min_dte: int = 21
    max_dte: int = 60
    target_dte: int = 45
    max_width_pct: float = 0.08
    calendar_min_iv_spread: float = 0.03
    calendar_max_strike_distance_pct: float = 0.015
    butterfly_max_middle_distance_pct: float = 0.015
    iron_condor_min_volatility_score: float = 0.5
    iron_condor_min_iv_rank: float = 0.5


class StrategySelector(Protocol):
    strategy_name: str

    def select(
        self,
        symbol: str,
        option_chain: OptionChain,
        regime_result: RegimeResult,
        settings: Any,
    ) -> list[OptionStrategyCandidate]:
        """Return zero or more candidates for one strategy family."""


class OptionsStrategySelector:
    """Combines all defined-risk options strategy selectors."""

    def __init__(self, selectors: list[StrategySelector] | None = None) -> None:
        self.selectors = selectors or [
            BullCallSpreadSelector(),
            BearPutSpreadSelector(),
            CalendarSpreadSelector(),
            LongButterflySelector(),
            IronCondorSelector(),
        ]

    def select(
        self,
        symbol: str,
        option_chain: OptionChain,
        regime_result: RegimeResult,
        settings: Any | None = None,
    ) -> list[OptionStrategyCandidate]:
        """Return valid, liquid, alert-only candidates sorted by descending score."""

        settings = settings or OptionsStrategySelectorSettings()
        liquid_chain = filter_liquid_contracts(option_chain, settings)
        if not liquid_chain.contracts:
            return []
        candidates: list[OptionStrategyCandidate] = []
        for selector in self.selectors:
            if isinstance(
                selector,
                (
                    BullCallSpreadSelector,
                    BearPutSpreadSelector,
                    CalendarSpreadSelector,
                    LongButterflySelector,
                    IronCondorSelector,
                ),
            ):
                selected = selector.select(
                    symbol,
                    liquid_chain.underlying_price,
                    liquid_chain,
                    regime_result,
                    settings,
                )
            else:
                selected = selector.select(symbol, liquid_chain, regime_result, settings)
            if selected is None:
                continue
            selected_candidates = [selected] if isinstance(selected, OptionStrategyCandidate) else selected
            for candidate in selected_candidates:
                candidate.warnings.append("Alert-only candidate; no real-money order execution is performed.")
                if not _is_valid_defined_risk(candidate):
                    continue
                is_liquid, _warnings = validate_strategy_liquidity(candidate, settings)
                if not is_liquid:
                    continue
                candidates.append(candidate)

        candidates.sort(key=lambda candidate: candidate.score, reverse=True)
        return candidates[: _setting(settings, "max_candidates_per_symbol", 5)]


def _contracts(option_chain: OptionChain, option_type: str, expiration: date) -> list[OptionContract]:
    return [
        contract
        for contract in option_chain.contracts
        if contract.option_type == option_type and contract.expiration == expiration
    ]


def _target_expiration(option_chain: OptionChain, settings: Any) -> date:
    expirations = sorted({contract.expiration for contract in option_chain.contracts})
    min_dte = _setting(settings, "min_dte", 21)
    max_dte = _setting(settings, "max_dte", 60)
    target_dte = _setting(settings, "target_dte", 45)
    eligible = [
        expiration
        for expiration in expirations
        if min_dte <= (expiration - option_chain.as_of.date()).days <= max_dte
    ]
    choices = eligible or expirations
    return min(choices, key=lambda expiration: abs((expiration - option_chain.as_of.date()).days - target_dte))


def _nearest(contracts: list[OptionContract], strike: float) -> OptionContract | None:
    if not contracts:
        return None
    return min(contracts, key=lambda contract: abs(contract.strike - strike))


def _nearest_above(
    contracts: list[OptionContract], strike: float, underlying_price: float, settings: Any
) -> OptionContract | None:
    max_width = underlying_price * _setting(settings, "max_width_pct", 0.08)
    candidates = [
        contract for contract in contracts if strike < contract.strike <= strike + max_width
    ]
    return min(candidates, key=lambda contract: contract.strike) if candidates else None


def _nearest_below(
    contracts: list[OptionContract], strike: float, underlying_price: float, settings: Any
) -> OptionContract | None:
    max_width = underlying_price * _setting(settings, "max_width_pct", 0.08)
    candidates = [
        contract for contract in contracts if strike - max_width <= contract.strike < strike
    ]
    return max(candidates, key=lambda contract: contract.strike) if candidates else None


def _is_valid_defined_risk(candidate: OptionStrategyCandidate) -> bool:
    if not candidate.legs or candidate.max_loss is None:
        candidate.warnings.append("Rejected: candidate must have legs and a calculable max loss.")
        return False
    for index, leg in enumerate(candidate.legs, start=1):
        if leg.action == LegAction.SELL.value and not _has_protective_long_leg(leg, candidate.legs):
            candidate.warnings.append(
                f"Rejected: leg {index} {leg.option.symbol} would create a naked short option."
            )
            return False
    return True


def _has_protective_long_leg(short_leg: OptionLeg, legs: list[OptionLeg]) -> bool:
    short = short_leg.option
    for leg in legs:
        option = leg.option
        if leg.action != LegAction.BUY.value:
            continue
        if option.option_type != short.option_type:
            continue
        if option.expiration < short.expiration:
            continue
        if option.expiration == short.expiration and option.strike != short.strike:
            return True
        if option.expiration > short.expiration and option.strike == short.strike:
            return True
    return False


def _setting(settings: Any, name: str, default: Any) -> Any:
    if isinstance(settings, dict):
        return settings.get(name, default)
    return getattr(settings, name, default)
