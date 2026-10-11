"""Alert text formatters."""

from __future__ import annotations

from quant_options_monitor.features.regime import RegimeResult
from quant_options_monitor.options.models import OptionStrategyCandidate


def format_options_candidate_alert(
    *,
    symbol: str,
    latest_price: float,
    regime_result: RegimeResult,
    candidate: OptionStrategyCandidate,
) -> str:
    """Format an options candidate for human-readable alerts."""

    lines = [
        f"[OPTIONS SIGNAL] {symbol.upper()} - {_title_case(candidate.strategy_name)} Candidate",
        f"Price: {latest_price:.2f}",
        f"Regime: {regime_result.regime}",
        f"Trend Score: {regime_result.trend_score:.2f}",
        f"Strategy: {_title_case(candidate.strategy_name)}",
        "Legs:",
    ]
    for leg in candidate.legs:
        option = leg.option
        lines.append(
            "  - "
            f"{leg.action.upper()} {leg.quantity} "
            f"{option.option_type.upper()} {option.strike:.2f} "
            f"exp {option.expiration.isoformat()} "
            f"bid {option.bid:.2f} ask {option.ask:.2f}"
        )
    lines.extend(
        [
            f"Max Loss: {candidate.max_loss}",
            f"Max Profit: {candidate.max_profit}",
            f"Breakevens: {candidate.breakevens}",
            "Reasons:",
        ]
    )
    lines.extend(f"  - {reason}" for reason in candidate.reasons)
    lines.append("Warnings:")
    if candidate.warnings:
        lines.extend(f"  - {warning}" for warning in candidate.warnings)
    else:
        lines.append("  - none")
    return "\n".join(lines)


def _title_case(value: str) -> str:
    return value.replace("_", " ").title()
