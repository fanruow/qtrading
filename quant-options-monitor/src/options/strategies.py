"""Options strategy selection and candidate construction."""

from __future__ import annotations

from datetime import date, datetime, timezone

from src.config import RiskConfig, StrategyConfig
from src.data.models import OptionContract, StrategyCandidate
from src.regime.classifier import MarketRegime


def _dte(expiration: date) -> int:
    return max((expiration - datetime.now(timezone.utc).date()).days, 0)


def _liquidity(contract: OptionContract, risk: RiskConfig) -> dict[str, bool]:
    return {
        "min_volume": contract.volume >= risk.min_option_volume,
        "min_open_interest": contract.open_interest >= risk.min_option_open_interest,
        "max_bid_ask_spread": contract.bid_ask_spread_pct <= risk.max_bid_ask_spread_pct,
    }


def _all_liquid(legs: list[OptionContract], risk: RiskConfig) -> dict[str, bool]:
    checks = [_liquidity(leg, risk) for leg in legs]
    return {key: all(item[key] for item in checks) for key in checks[0]} if checks else {}


def _nearest(contracts: list[OptionContract], strike: float, right: str) -> OptionContract:
    side = [c for c in contracts if c.right == right]
    if not side:
        raise ValueError(f"No {right} contracts found")
    return min(side, key=lambda c: abs(c.strike - strike))


class OptionsStrategySelector:
    """Selects alertable multi-leg option candidates from regime and chain data."""

    def __init__(self, risk: RiskConfig, strategy: StrategyConfig) -> None:
        self.risk = risk
        self.strategy = strategy

    def select(
        self,
        symbol: str,
        spot: float,
        regime: MarketRegime,
        chain: list[OptionContract],
        vol_features: dict[str, float],
    ) -> list[StrategyCandidate]:
        if not chain:
            return []
        if regime == MarketRegime.BULLISH_TREND:
            return [self.bull_call_spread(symbol, spot, chain)]
        if regime == MarketRegime.BEARISH_TREND:
            return [self.bear_put_spread(symbol, spot, chain)]
        if regime == MarketRegime.HIGH_VOLATILITY:
            return [self.iron_condor(symbol, spot, chain)]
        if regime == MarketRegime.LOW_VOLATILITY:
            return [self.calendar_spread(symbol, spot, chain)]
        return [self.butterfly(symbol, spot, chain)]

    def bull_call_spread(self, symbol: str, spot: float, chain: list[OptionContract]) -> StrategyCandidate:
        long_call = _nearest(chain, spot * 1.00, "call")
        short_call = _nearest(chain, spot * 1.05, "call")
        debit = max(long_call.mid - short_call.mid, 0.01)
        width = short_call.strike - long_call.strike
        return StrategyCandidate(
            symbol=symbol,
            strategy="bull_call_spread",
            candidate_strikes=[long_call.strike, short_call.strike],
            dte=_dte(long_call.expiration),
            max_loss=debit * 100,
            max_profit=max(width - debit, 0) * 100,
            breakeven=[long_call.strike + debit],
            liquidity_filters=_all_liquid([long_call, short_call], self.risk),
            reason="Bullish trend favors defined-risk upside exposure.",
            legs=[long_call, short_call],
        )

    def bear_put_spread(self, symbol: str, spot: float, chain: list[OptionContract]) -> StrategyCandidate:
        long_put = _nearest(chain, spot * 1.00, "put")
        short_put = _nearest(chain, spot * 0.95, "put")
        debit = max(long_put.mid - short_put.mid, 0.01)
        width = long_put.strike - short_put.strike
        return StrategyCandidate(
            symbol=symbol,
            strategy="bear_put_spread",
            candidate_strikes=[long_put.strike, short_put.strike],
            dte=_dte(long_put.expiration),
            max_loss=debit * 100,
            max_profit=max(width - debit, 0) * 100,
            breakeven=[long_put.strike - debit],
            liquidity_filters=_all_liquid([long_put, short_put], self.risk),
            reason="Bearish trend favors defined-risk downside exposure.",
            legs=[long_put, short_put],
        )

    def calendar_spread(self, symbol: str, spot: float, chain: list[OptionContract]) -> StrategyCandidate:
        calls = sorted([c for c in chain if c.right == "call"], key=lambda c: (c.expiration, abs(c.strike - spot)))
        near = calls[0]
        far_candidates = [c for c in calls if c.strike == near.strike and c.expiration > near.expiration]
        far = far_candidates[-1] if far_candidates else near
        debit = max(far.mid - near.mid, 0.01)
        return StrategyCandidate(
            symbol=symbol,
            strategy="calendar_spread",
            candidate_strikes=[near.strike],
            dte=_dte(near.expiration),
            max_loss=debit * 100,
            max_profit=None,
            breakeven=[],
            liquidity_filters=_all_liquid([near, far], self.risk),
            reason="Low volatility favors long-vega structures with limited debit.",
            legs=[near, far],
        )

    def butterfly(self, symbol: str, spot: float, chain: list[OptionContract]) -> StrategyCandidate:
        lower = _nearest(chain, spot * 0.95, "call")
        middle = _nearest(chain, spot, "call")
        upper = _nearest(chain, spot * 1.05, "call")
        debit = max(lower.mid - 2 * middle.mid + upper.mid, 0.01)
        width = middle.strike - lower.strike
        return StrategyCandidate(
            symbol=symbol,
            strategy="butterfly",
            candidate_strikes=[lower.strike, middle.strike, upper.strike],
            dte=_dte(middle.expiration),
            max_loss=debit * 100,
            max_profit=max(width - debit, 0) * 100,
            breakeven=[lower.strike + debit, upper.strike - debit],
            liquidity_filters=_all_liquid([lower, middle, upper], self.risk),
            reason="Range-bound regime favors centered, defined-risk convex payoff.",
            legs=[lower, middle, upper],
        )

    def iron_condor(self, symbol: str, spot: float, chain: list[OptionContract]) -> StrategyCandidate:
        short_put = _nearest(chain, spot * 0.95, "put")
        long_put = _nearest(chain, spot * 0.90, "put")
        short_call = _nearest(chain, spot * 1.05, "call")
        long_call = _nearest(chain, spot * 1.10, "call")
        credit = max(short_put.mid + short_call.mid - long_put.mid - long_call.mid, 0.01)
        width = min(short_put.strike - long_put.strike, long_call.strike - short_call.strike)
        return StrategyCandidate(
            symbol=symbol,
            strategy="iron_condor",
            candidate_strikes=[long_put.strike, short_put.strike, short_call.strike, long_call.strike],
            dte=_dte(short_put.expiration),
            max_loss=max(width - credit, 0) * 100,
            max_profit=credit * 100,
            breakeven=[short_put.strike - credit, short_call.strike + credit],
            liquidity_filters=_all_liquid([long_put, short_put, short_call, long_call], self.risk),
            reason="High implied volatility can support defined-risk premium selling.",
            legs=[long_put, short_put, short_call, long_call],
        )
