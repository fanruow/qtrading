"""Bull call spread candidate generation."""

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


class BullCallSpreadSelector:
    """Generate defined-risk bullish call debit spread candidates."""

    strategy_name = "bull_call_spread"

    def select(
        self,
        symbol: str,
        underlying_price: float,
        option_chain: OptionChain,
        regime_result: RegimeResult,
        settings: Any,
    ) -> OptionStrategyCandidate | None:
        if regime_result.trend_score <= 0.65:
            return None
        if regime_result.regime != MarketRegime.BULLISH_TREND and abs(regime_result.volatility_score) >= 1.0:
            return None

        calls = [
            contract
            for contract in option_chain.contracts
            if contract.option_type == "call"
            and 30 <= _dte_from_chain(option_chain, contract) <= 60
            and contract.delta is not None
        ]
        long_candidates = [
            contract for contract in calls if 0.45 <= float(contract.delta) <= 0.60
        ]
        short_candidates = [
            contract for contract in calls if 0.20 <= float(contract.delta) <= 0.35
        ]

        liquid_longs = [
            contract for contract in long_candidates if _is_liquid(contract, settings)
        ]
        liquid_shorts = [
            contract for contract in short_candidates if _is_liquid(contract, settings)
        ]
        if not liquid_longs or not liquid_shorts:
            return None

        best_candidate: OptionStrategyCandidate | None = None
        for long_call in sorted(liquid_longs, key=lambda contract: abs(contract.delta or 0 - 0.52)):
            same_expiration_shorts = [
                contract
                for contract in liquid_shorts
                if contract.expiration == long_call.expiration and contract.strike > long_call.strike
            ]
            if not same_expiration_shorts:
                continue
            short_call = min(
                same_expiration_shorts,
                key=lambda contract: abs(float(contract.delta or 0) - 0.28),
            )
            candidate = self._build_candidate(
                symbol=symbol,
                underlying_price=underlying_price,
                long_call=long_call,
                short_call=short_call,
                regime_result=regime_result,
                settings=settings,
            )
            if best_candidate is None or candidate.score > best_candidate.score:
                best_candidate = candidate

        return best_candidate

    def _build_candidate(
        self,
        *,
        symbol: str,
        underlying_price: float,
        long_call: OptionContract,
        short_call: OptionContract,
        regime_result: RegimeResult,
        settings: Any,
    ) -> OptionStrategyCandidate:
        debit = round(long_call.ask - short_call.bid, 4)
        width = round(short_call.strike - long_call.strike, 4)
        max_loss = round(debit * 100, 2)
        max_profit = round(width * 100 - max_loss, 2)
        reward_risk = max_profit / max_loss if max_loss > 0 else 0.0
        liquidity_score = _liquidity_score(long_call, short_call, settings)
        score = _score(
            trend_score=regime_result.trend_score,
            liquidity_score=liquidity_score,
            reward_risk=reward_risk,
        )

        return OptionStrategyCandidate(
            strategy_name=self.strategy_name,
            underlying_symbol=symbol,
            legs=[
                OptionLeg(action=LegAction.BUY, option=long_call, quantity=1),
                OptionLeg(action=LegAction.SELL, option=short_call, quantity=1),
            ],
            max_loss=max_loss,
            max_profit=max(max_profit, 0.0),
            breakevens=[round(long_call.strike + debit, 2)],
            estimated_debit_or_credit=round(-max_loss, 2),
            score=score,
            reasons=[
                "Bullish trend score is above threshold for a defined-risk call debit spread.",
                (
                    f"Buy call delta {float(long_call.delta or 0):.2f} and sell call delta "
                    f"{float(short_call.delta or 0):.2f} are within target ranges."
                ),
                (
                    f"Net debit is {debit:.2f}; max loss is {max_loss:.2f}, "
                    f"max profit is {max(max_profit, 0.0):.2f}."
                ),
                f"Underlying reference price is {underlying_price:.2f}.",
            ],
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
    long_call: OptionContract, short_call: OptionContract, settings: Any
) -> float:
    max_spread_pct = _setting(settings, "max_bid_ask_spread_pct", 0.15)
    leg_scores = []
    for contract in (long_call, short_call):
        spread_score = max(0.0, 1.0 - contract.bid_ask_spread_pct / max_spread_pct)
        volume_score = min(contract.volume / max(_setting(settings, "min_option_volume", 100), 1), 3.0) / 3.0
        oi_score = (
            min(contract.open_interest / max(_setting(settings, "min_option_open_interest", 500), 1), 3.0)
            / 3.0
        )
        leg_scores.append((spread_score + volume_score + oi_score) / 3)
    return sum(leg_scores) / len(leg_scores)


def _score(trend_score: float, liquidity_score: float, reward_risk: float) -> float:
    reward_component = min(reward_risk / 2.0, 1.0)
    raw = trend_score * 55 + liquidity_score * 25 + reward_component * 20
    return round(max(0.0, min(raw, 100.0)), 4)


def _setting(settings: Any, name: str, default: Any) -> Any:
    if isinstance(settings, dict):
        return settings.get(name, default)
    return getattr(settings, name, default)
