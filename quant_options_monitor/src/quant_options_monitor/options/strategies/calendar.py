"""Calendar spread candidate generation."""

from __future__ import annotations

from typing import Any

from quant_options_monitor.features.regime import MarketRegime, RegimeResult
from quant_options_monitor.options.models import (
    LegAction,
    OptionChain,
    OptionContract,
    OptionLeg,
    OptionStrategyCandidate,
)
from quant_options_monitor.risk.trade_filters import is_option_liquid


class CalendarSpreadSelector:
    """Generate call and put calendar spread candidates."""

    strategy_name = "calendar_spread"

    def select(
        self,
        symbol: str,
        underlying_price: float,
        option_chain: OptionChain,
        regime_result: RegimeResult,
        settings: Any,
    ) -> list[OptionStrategyCandidate]:
        if not _expects_price_near_target(regime_result):
            return []

        candidates: list[OptionStrategyCandidate] = []
        for option_type in ("call", "put"):
            candidate = self._select_for_type(
                symbol=symbol,
                underlying_price=underlying_price,
                option_chain=option_chain,
                regime_result=regime_result,
                settings=settings,
                option_type=option_type,
            )
            if candidate is not None:
                candidates.append(candidate)

        candidates.sort(key=lambda candidate: candidate.score, reverse=True)
        return candidates

    def _select_for_type(
        self,
        *,
        symbol: str,
        underlying_price: float,
        option_chain: OptionChain,
        regime_result: RegimeResult,
        settings: Any,
        option_type: str,
    ) -> OptionStrategyCandidate | None:
        target_candidates = [
            contract
            for contract in option_chain.contracts
            if contract.option_type == option_type
            and abs(contract.strike - underlying_price) / underlying_price <= _setting(
                settings, "calendar_max_strike_distance_pct", 0.015
            )
            and contract.implied_volatility is not None
        ]
        short_candidates = [
            contract
            for contract in target_candidates
            if 7 <= _dte_from_chain(option_chain, contract) <= 30 and _is_liquid(contract, settings)
        ]
        long_candidates = [
            contract
            for contract in target_candidates
            if 30 <= _dte_from_chain(option_chain, contract) <= 90 and _is_liquid(contract, settings)
        ]
        if not short_candidates or not long_candidates:
            return None

        best_candidate: OptionStrategyCandidate | None = None
        for short_leg in sorted(short_candidates, key=lambda contract: abs(contract.strike - underlying_price)):
            same_strike_longs = [
                contract
                for contract in long_candidates
                if contract.strike == short_leg.strike and contract.expiration > short_leg.expiration
            ]
            if not same_strike_longs:
                continue
            for long_leg in sorted(
                same_strike_longs,
                key=lambda contract: _dte_from_chain(option_chain, contract),
            ):
                iv_spread = float(short_leg.implied_volatility or 0) - float(
                    long_leg.implied_volatility or 0
                )
                if iv_spread < _setting(settings, "calendar_min_iv_spread", 0.03):
                    continue
                candidate = self._build_candidate(
                    symbol=symbol,
                    underlying_price=underlying_price,
                    short_leg=short_leg,
                    long_leg=long_leg,
                    iv_spread=iv_spread,
                    regime_result=regime_result,
                    settings=settings,
                    option_type=option_type,
                )
                if best_candidate is None or candidate.score > best_candidate.score:
                    best_candidate = candidate

        return best_candidate

    def _build_candidate(
        self,
        *,
        symbol: str,
        underlying_price: float,
        short_leg: OptionContract,
        long_leg: OptionContract,
        iv_spread: float,
        regime_result: RegimeResult,
        settings: Any,
        option_type: str,
    ) -> OptionStrategyCandidate:
        debit = round(long_leg.ask - short_leg.bid, 4)
        max_loss = round(max(debit, 0.01) * 100, 2)
        liquidity_score = _liquidity_score(short_leg, long_leg, settings)
        distance_pct = abs(short_leg.strike - underlying_price) / underlying_price
        distance_score = max(
            0.0,
            1.0 - distance_pct / _setting(settings, "calendar_max_strike_distance_pct", 0.015),
        )
        score = _score(
            iv_spread=iv_spread,
            liquidity_score=liquidity_score,
            distance_score=distance_score,
            regime_result=regime_result,
            settings=settings,
        )

        return OptionStrategyCandidate(
            strategy_name=f"{option_type}_calendar_spread",
            underlying_symbol=symbol,
            legs=[
                OptionLeg(action=LegAction.BUY, option=long_leg, quantity=1),
                OptionLeg(action=LegAction.SELL, option=short_leg, quantity=1),
            ],
            max_loss=max_loss,
            max_profit=None,
            breakevens=[],
            estimated_debit_or_credit=round(-max_loss, 2),
            score=score,
            reasons=[
                (
                    f"{option_type.title()} calendar uses the same strike and option type "
                    "across short and long expirations."
                ),
                (
                    f"Front IV exceeds back IV by {iv_spread:.2%}, meeting the favorable "
                    "term-structure threshold."
                ),
                (
                    f"Target strike {short_leg.strike:.2f} is within "
                    f"{distance_pct:.2%} of underlying price {underlying_price:.2f}."
                ),
            ],
            warnings=[
                "Calendar max profit is path-dependent and approximate",
                "Avoid holding short leg too close to expiration without active management",
            ],
        )


def _expects_price_near_target(regime_result: RegimeResult) -> bool:
    return (
        regime_result.regime in {MarketRegime.RANGE_BOUND, MarketRegime.LOW_VOLATILITY}
        or regime_result.range_score >= 0.5
        or abs(regime_result.trend_score) <= 0.35
    )


def _dte_from_chain(option_chain: OptionChain, contract: OptionContract) -> int:
    return max((contract.expiration - option_chain.as_of.date()).days, 0)


def _is_liquid(contract: OptionContract, settings: Any) -> bool:
    return is_option_liquid(
        contract=contract,
        min_volume=_setting(settings, "min_option_volume", 100),
        min_open_interest=_setting(settings, "min_option_open_interest", 500),
        max_spread_pct=_setting(settings, "max_bid_ask_spread_pct", 0.15),
    )


def _liquidity_score(
    short_leg: OptionContract, long_leg: OptionContract, settings: Any
) -> float:
    max_spread_pct = _setting(settings, "max_bid_ask_spread_pct", 0.15)
    leg_scores = []
    for contract in (short_leg, long_leg):
        spread_score = max(0.0, 1.0 - contract.bid_ask_spread_pct / max_spread_pct)
        volume_score = min(contract.volume / max(_setting(settings, "min_option_volume", 100), 1), 3.0) / 3.0
        oi_score = (
            min(contract.open_interest / max(_setting(settings, "min_option_open_interest", 500), 1), 3.0)
            / 3.0
        )
        leg_scores.append((spread_score + volume_score + oi_score) / 3)
    return sum(leg_scores) / len(leg_scores)


def _score(
    *,
    iv_spread: float,
    liquidity_score: float,
    distance_score: float,
    regime_result: RegimeResult,
    settings: Any,
) -> float:
    iv_component = min(iv_spread / max(_setting(settings, "calendar_min_iv_spread", 0.03), 0.0001), 2.0) / 2.0
    regime_component = max(regime_result.range_score, max(-regime_result.volatility_score, 0.0))
    raw = iv_component * 45 + liquidity_score * 25 + distance_score * 20 + regime_component * 10
    return round(max(0.0, min(raw, 100.0)), 4)


def _setting(settings: Any, name: str, default: Any) -> Any:
    if isinstance(settings, dict):
        return settings.get(name, default)
    return getattr(settings, name, default)
