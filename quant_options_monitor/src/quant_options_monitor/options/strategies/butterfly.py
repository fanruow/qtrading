"""Long butterfly spread candidate generation."""

from __future__ import annotations

from typing import Any

from quant_options_monitor.options.models import (
    LegAction,
    OptionChain,
    OptionContract,
    OptionLeg,
    OptionStrategyCandidate,
)
from quant_options_monitor.features.regime import RegimeResult
from quant_options_monitor.risk.trade_filters import is_option_liquid


class LongButterflySelector:
    """Generate centered 1:-2:1 call butterfly candidates."""

    strategy_name = "long_butterfly"

    def select(
        self,
        symbol: str,
        underlying_price: float,
        option_chain: OptionChain,
        regime_result: RegimeResult,
        settings: Any,
    ) -> OptionStrategyCandidate | None:
        if regime_result.range_score <= 0.65:
            return None

        calls = [
            contract
            for contract in option_chain.contracts
            if contract.option_type == "call"
            and 7 <= _dte_from_chain(option_chain, contract) <= 45
            and _is_liquid(contract, settings)
        ]
        if not calls:
            return None

        expirations = sorted({contract.expiration for contract in calls})
        best_candidate: OptionStrategyCandidate | None = None
        for expiration in expirations:
            expiration_calls = sorted(
                [contract for contract in calls if contract.expiration == expiration],
                key=lambda contract: contract.strike,
            )
            middle = _nearest(expiration_calls, underlying_price)
            if middle is None:
                continue
            if abs(middle.strike - underlying_price) / underlying_price > _setting(
                settings, "butterfly_max_middle_distance_pct", 0.015
            ):
                continue
            for lower, upper in _symmetric_wing_pairs(expiration_calls, middle):
                candidate = self._build_candidate(
                    symbol=symbol,
                    underlying_price=underlying_price,
                    lower=lower,
                    middle=middle,
                    upper=upper,
                    regime_result=regime_result,
                    settings=settings,
                )
                if candidate is None:
                    continue
                if best_candidate is None or candidate.score > best_candidate.score:
                    best_candidate = candidate

        return best_candidate

    def _build_candidate(
        self,
        *,
        symbol: str,
        underlying_price: float,
        lower: OptionContract,
        middle: OptionContract,
        upper: OptionContract,
        regime_result: RegimeResult,
        settings: Any,
    ) -> OptionStrategyCandidate | None:
        debit = round(lower.ask - 2 * middle.bid + upper.ask, 4)
        max_loss = round(max(debit, 0.01) * 100, 2)
        wing_width = round(middle.strike - lower.strike, 4)
        max_profit = round(wing_width * 100 - max_loss, 2)
        if max_profit <= 0:
            return None
        distance_pct = abs(middle.strike - underlying_price) / underlying_price
        liquidity_score = _liquidity_score(lower, middle, upper, settings)
        distance_score = max(
            0.0,
            1.0 - distance_pct / _setting(settings, "butterfly_max_middle_distance_pct", 0.015),
        )
        score = _score(
            range_score=regime_result.range_score,
            liquidity_score=liquidity_score,
            distance_score=distance_score,
            reward_risk=max_profit / max_loss if max_loss > 0 else 0.0,
        )

        return OptionStrategyCandidate(
            strategy_name=self.strategy_name,
            underlying_symbol=symbol,
            legs=[
                OptionLeg(action=LegAction.BUY, option=lower, quantity=1),
                OptionLeg(action=LegAction.SELL, option=middle, quantity=2),
                OptionLeg(action=LegAction.BUY, option=upper, quantity=1),
            ],
            max_loss=max_loss,
            max_profit=max_profit,
            breakevens=[round(lower.strike + max_loss / 100, 2), round(upper.strike - max_loss / 100, 2)],
            estimated_debit_or_credit=round(-max_loss, 2),
            score=score,
            reasons=[
                "Range score is above threshold for a centered long butterfly.",
                (
                    f"Middle strike {middle.strike:.2f} is near underlying price "
                    f"{underlying_price:.2f}."
                ),
                (
                    f"Symmetric wings selected at {lower.strike:.2f} and {upper.strike:.2f} "
                    f"around middle strike {middle.strike:.2f}."
                ),
            ],
        )


def _dte_from_chain(option_chain: OptionChain, contract: OptionContract) -> int:
    return max((contract.expiration - option_chain.as_of.date()).days, 0)


def _nearest(contracts: list[OptionContract], strike: float) -> OptionContract | None:
    if not contracts:
        return None
    return min(contracts, key=lambda contract: abs(contract.strike - strike))


def _symmetric_wing_pairs(
    contracts: list[OptionContract], middle: OptionContract
) -> list[tuple[OptionContract, OptionContract]]:
    by_strike = {contract.strike: contract for contract in contracts}
    distances = sorted(
        {
            round(abs(contract.strike - middle.strike), 8)
            for contract in contracts
            if contract.strike != middle.strike
        }
    )
    pairs: list[tuple[OptionContract, OptionContract]] = []
    for distance in distances:
        lower = by_strike.get(round(middle.strike - distance, 8))
        upper = by_strike.get(round(middle.strike + distance, 8))
        if lower is not None and upper is not None:
            pairs.append((lower, upper))
    return pairs


def _is_liquid(contract: OptionContract, settings: Any) -> bool:
    return is_option_liquid(
        contract=contract,
        min_volume=_setting(settings, "min_option_volume", 100),
        min_open_interest=_setting(settings, "min_option_open_interest", 500),
        max_spread_pct=_setting(settings, "max_bid_ask_spread_pct", 0.15),
    )


def _liquidity_score(
    lower: OptionContract, middle: OptionContract, upper: OptionContract, settings: Any
) -> float:
    max_spread_pct = _setting(settings, "max_bid_ask_spread_pct", 0.15)
    leg_scores = []
    for contract in (lower, middle, upper):
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
    range_score: float,
    liquidity_score: float,
    distance_score: float,
    reward_risk: float,
) -> float:
    reward_component = min(reward_risk / 2.0, 1.0)
    raw = range_score * 45 + liquidity_score * 25 + distance_score * 20 + reward_component * 10
    return round(max(0.0, min(raw, 100.0)), 4)


def _setting(settings: Any, name: str, default: Any) -> Any:
    if isinstance(settings, dict):
        return settings.get(name, default)
    return getattr(settings, name, default)
