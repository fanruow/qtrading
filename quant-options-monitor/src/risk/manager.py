"""Risk management checks for alert-only strategy candidates."""

from __future__ import annotations

from dataclasses import dataclass

from src.config import RiskConfig
from src.data.models import StrategyCandidate


@dataclass(frozen=True)
class RiskDecision:
    approved: bool
    reasons: list[str]


class RiskManager:
    """Applies portfolio and options liquidity risk checks before alerting."""

    def __init__(self, config: RiskConfig, portfolio_value: float) -> None:
        self.config = config
        self.portfolio_value = portfolio_value

    def evaluate(
        self,
        candidate: StrategyCandidate,
        current_symbol_exposure: float = 0.0,
        current_drawdown: float = 0.0,
    ) -> RiskDecision:
        reasons: list[str] = []
        max_position_risk = self.portfolio_value * self.config.max_position_risk_pct
        if candidate.max_loss is not None and candidate.max_loss > max_position_risk:
            reasons.append(f"max loss {candidate.max_loss:.2f} exceeds {max_position_risk:.2f}")
        max_exposure = self.portfolio_value * self.config.max_symbol_exposure_pct
        if current_symbol_exposure > max_exposure:
            reasons.append(f"symbol exposure {current_symbol_exposure:.2f} exceeds {max_exposure:.2f}")
        if current_drawdown > self.config.max_portfolio_drawdown_pct:
            reasons.append(f"portfolio drawdown {current_drawdown:.2%} exceeds limit")
        failed_liquidity = [name for name, ok in candidate.liquidity_filters.items() if not ok]
        if failed_liquidity:
            reasons.append(f"liquidity filters failed: {', '.join(failed_liquidity)}")
        return RiskDecision(approved=not reasons, reasons=reasons)
