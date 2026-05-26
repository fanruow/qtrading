"""Bear put spread candidate generation."""

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


class BearPutSpreadSelector:
    """Generate defined-risk bearish put debit spread candidates."""

    strategy_name = "bear_put_spread"

    def select(
        self,
        symbol: str,
        underlying_price: float,
        option_chain: OptionChain,
        regime_result: RegimeResult,
        settings: Any,
    ) -> OptionStrategyCandidate | None:
        if regime_result.trend_score >= -0.65:
            return None
        if regime_result.regime != MarketRegime.BEARISH_TREND:
            return None

        puts = [
            contract
            for contract in option_chain.contracts
            if contract.option_type == "put"
            and 30 <= _dte_from_chain(option_chain, contract) <= 60
            and contract.delta is not None
        ]
        long_candidates = [
            contract for contract in puts if -0.60 <= float(contract.delta) <= -0.45
        ]
        short_candidates = [
            contract for contract in puts if -0.35 <= float(contract.delta) <= -0.20
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
        for long_put in sorted(liquid_longs, key=lambda contract: abs(float(contract.delta or 0) + 0.52)):
            same_expiration_shorts = [
                contract
                for contract in liquid_shorts
                if contract.expiration == long_put.expiration and contract.strike < long_put.strike
            ]
            if not same_expiration_shorts:
                continue
            short_put = min(
                same_expiration_shorts,
                key=lambda contract: abs(float(contract.delta or 0) + 0.28),
            )
            candidate = self._build_candidate(
                symbol=symbol,
                underlying_price=underlying_price,
                long_put=long_put,
                short_put=short_put,
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
        long_put: OptionContract,
        short_put: OptionContract,
        regime_result: RegimeResult,
        settings: Any,
    ) -> OptionStrategyCandidate:
        debit = round(long_put.ask - short_put.bid, 4)
        width = round(long_put.strike - short_put.strike, 4)
        max_loss = round(debit * 100, 2)
        max_profit = round(width * 100 - max_loss, 2)
        reward_risk = max_profit / max_loss if max_loss > 0 else 0.0
        liquidity_score = _liquidity_score(long_put, short_put, settings)
        score = _score(
            trend_score=abs(regime_result.trend_score),
            liquidity_score=liquidity_score,
            reward_risk=reward_risk,
        )

        return OptionStrategyCandidate(
            strategy_name=self.strategy_name,
            underlying_symbol=symbol,
            legs=[
                OptionLeg(action=LegAction.BUY, option=long_put, quantity=1),
                OptionLeg(action=LegAction.SELL, option=short_put, quantity=1),
            ],
            max_loss=max_loss,
            max_profit=max(max_profit, 0.0),
            breakevens=[round(long_put.strike - debit, 2)],
            estimated_debit_or_credit=round(-max_loss, 2),
            score=score,
            reasons=[
                "Bearish trend score is below threshold for a defined-risk put debit spread.",
                (
                    f"Buy put delta {float(long_put.delta or 0):.2f} and sell put delta "
                    f"{float(short_put.delta or 0):.2f} are within target ranges."
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


def _liquidity_score(long_put: OptionContract, short_put: OptionContract, settings: Any) -> float:
    max_spread_pct = _setting(settings, "max_bid_ask_spread_pct", 0.15)
    leg_scores = []
    for contract in (long_put, short_put):
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
