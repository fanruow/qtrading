from __future__ import annotations

from src.config import AppConfig
from src.data.providers import SyntheticMarketDataProvider
from src.options.strategies import OptionsStrategySelector
from src.regime.classifier import MarketRegime
from src.risk.manager import RiskManager


def test_strategy_selector_outputs_required_fields() -> None:
    config = AppConfig()
    provider = SyntheticMarketDataProvider()
    expiration = provider.get_expirations("SPY")[0]
    chain = provider.get_option_chain("SPY", expiration)
    selector = OptionsStrategySelector(config.risk, config.strategy)

    candidate = selector.select("SPY", 100.0, MarketRegime.BULLISH_TREND, chain, {})[0]

    assert candidate.strategy == "bull_call_spread"
    assert candidate.candidate_strikes
    assert candidate.dte > 0
    assert candidate.max_loss is not None
    assert candidate.breakeven
    assert candidate.reason


def test_risk_manager_rejects_oversized_loss() -> None:
    config = AppConfig()
    provider = SyntheticMarketDataProvider()
    chain = provider.get_option_chain("SPY", provider.get_expirations("SPY")[0])
    candidate = OptionsStrategySelector(config.risk, config.strategy).bull_call_spread("SPY", 100.0, chain)
    decision = RiskManager(config.risk, portfolio_value=50).evaluate(candidate)
    assert not decision.approved
