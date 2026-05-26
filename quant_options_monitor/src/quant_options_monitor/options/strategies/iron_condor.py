"""Iron condor candidate generation."""

from __future__ import annotations

from typing import Any

from quant_options_monitor.features.regime import RegimeResult
from quant_options_monitor.options.models import (
    LegAction,
    OptionChain,
    OptionContract,
    OptionLeg,
    OptionStrategyCandidate,
)
from quant_options_monitor.risk.trade_filters import is_option_liquid


class IronCondorSelector:
    """Generate defined-risk short premium iron condor candidates."""

    strategy_name = "iron_condor"

    def select(
        self,
        symbol: str,
        underlying_price: float,
        option_chain: OptionChain,
        regime_result: RegimeResult,
        settings: Any,
    ) -> OptionStrategyCandidate | None:
        if not (-0.25 <= regime_result.trend_score <= 0.25):
            return None
        if regime_result.range_score <= 0.60:
            return None
        if not _volatility_is_elevated(regime_result, settings):
            return None

        calls = [
            contract
            for contract in option_chain.contracts
            if contract.option_type == "call"
            and 30 <= _dte_from_chain(option_chain, contract) <= 45
            and contract.delta is not None
            and _is_liquid(contract, settings)
        ]
        puts = [
            contract
            for contract in option_chain.contracts
            if contract.option_type == "put"
            and 30 <= _dte_from_chain(option_chain, contract) <= 45
            and contract.delta is not None
            and _is_liquid(contract, settings)
        ]
        short_calls = [contract for contract in calls if 0.15 <= float(contract.delta) <= 0.25]
        short_puts = [contract for contract in puts if -0.25 <= float(contract.delta) <= -0.15]
        if not short_calls or not short_puts:
            return None

        best_candidate: OptionStrategyCandidate | None = None
        for short_put in sorted(short_puts, key=lambda contract: abs(float(contract.delta or 0) + 0.20)):
            long_put = _nearest_further_otm_put(puts, short_put)
            if long_put is None:
                continue
            for short_call in sorted(short_calls, key=lambda contract: abs(float(contract.delta or 0) - 0.20)):
                if short_call.expiration != short_put.expiration:
                    continue
                long_call = _nearest_further_otm_call(calls, short_call)
                if long_call is None:
                    continue
                candidate = self._build_candidate(
                    symbol=symbol,
                    underlying_price=underlying_price,
                    long_put=long_put,
                    short_put=short_put,
                    short_call=short_call,
                    long_call=long_call,
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
        long_put: OptionContract,
        short_put: OptionContract,
        short_call: OptionContract,
        long_call: OptionContract,
        regime_result: RegimeResult,
        settings: Any,
    ) -> OptionStrategyCandidate | None:
        put_width = round(short_put.strike - long_put.strike, 4)
        call_width = round(long_call.strike - short_call.strike, 4)
        if put_width <= 0 or call_width <= 0:
            return None
        wing_width = min(put_width, call_width)
        credit = round(short_put.bid + short_call.bid - long_put.ask - long_call.ask, 4)
        if credit <= 0:
            return None

        max_profit = round(credit * 100, 2)
        max_loss = round(wing_width * 100 - max_profit, 2)
        if max_loss <= 0:
            return None

        liquidity_score = _liquidity_score(long_put, short_put, short_call, long_call, settings)
        credit_width_score = min(max_profit / (wing_width * 100), 1.0)
        score = _score(
            range_score=regime_result.range_score,
            volatility_score=regime_result.volatility_score,
            liquidity_score=liquidity_score,
            credit_width_score=credit_width_score,
        )

        return OptionStrategyCandidate(
            strategy_name=self.strategy_name,
            underlying_symbol=symbol,
            legs=[
                OptionLeg(action=LegAction.SELL, option=short_put, quantity=1),
                OptionLeg(action=LegAction.BUY, option=long_put, quantity=1),
                OptionLeg(action=LegAction.SELL, option=short_call, quantity=1),
                OptionLeg(action=LegAction.BUY, option=long_call, quantity=1),
            ],
            max_loss=max_loss,
            max_profit=max_profit,
            breakevens=[round(short_put.strike - credit, 2), round(short_call.strike + credit, 2)],
            estimated_debit_or_credit=max_profit,
            score=score,
            reasons=[
                "Neutral trend and strong range score support a defined-risk iron condor.",
                (
                    f"Short put delta {float(short_put.delta or 0):.2f} and short call delta "
                    f"{float(short_call.delta or 0):.2f} are within target ranges."
                ),
                (
                    f"Net credit is {credit:.2f}; max profit is {max_profit:.2f}, "
                    f"max loss is {max_loss:.2f}."
                ),
                f"Underlying reference price is {underlying_price:.2f}.",
            ],
        )


def _volatility_is_elevated(regime_result: RegimeResult, settings: Any) -> bool:
    threshold = _setting(settings, "iron_condor_min_volatility_score", 0.5)
    if regime_result.volatility_score >= threshold:
        return True
    iv_rank = getattr(regime_result, "iv_rank", None)
    return iv_rank is not None and iv_rank >= _setting(settings, "iron_condor_min_iv_rank", 0.5)


def _dte_from_chain(option_chain: OptionChain, contract: OptionContract) -> int:
    return max((contract.expiration - option_chain.as_of.date()).days, 0)


def _nearest_further_otm_put(
    puts: list[OptionContract], short_put: OptionContract
) -> OptionContract | None:
    candidates = [
        contract
        for contract in puts
        if contract.expiration == short_put.expiration and contract.strike < short_put.strike
    ]
    return max(candidates, key=lambda contract: contract.strike) if candidates else None


def _nearest_further_otm_call(
    calls: list[OptionContract], short_call: OptionContract
) -> OptionContract | None:
    candidates = [
        contract
        for contract in calls
        if contract.expiration == short_call.expiration and contract.strike > short_call.strike
    ]
    return min(candidates, key=lambda contract: contract.strike) if candidates else None


def _is_liquid(contract: OptionContract, settings: Any) -> bool:
    return is_option_liquid(
        contract=contract,
        min_volume=_setting(settings, "min_option_volume", 100),
        min_open_interest=_setting(settings, "min_option_open_interest", 500),
        max_spread_pct=_setting(settings, "max_bid_ask_spread_pct", 0.15),
    )


def _liquidity_score(
    long_put: OptionContract,
    short_put: OptionContract,
    short_call: OptionContract,
    long_call: OptionContract,
    settings: Any,
) -> float:
    max_spread_pct = _setting(settings, "max_bid_ask_spread_pct", 0.15)
    leg_scores = []
    for contract in (long_put, short_put, short_call, long_call):
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
    volatility_score: float,
    liquidity_score: float,
    credit_width_score: float,
) -> float:
    volatility_component = max(0.0, min(volatility_score, 1.0))
    raw = range_score * 35 + volatility_component * 25 + liquidity_score * 25 + credit_width_score * 15
    return round(max(0.0, min(raw, 100.0)), 4)


def _setting(settings: Any, name: str, default: Any) -> Any:
    if isinstance(settings, dict):
        return settings.get(name, default)
    return getattr(settings, name, default)
