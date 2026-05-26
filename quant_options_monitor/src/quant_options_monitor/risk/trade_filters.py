"""Options liquidity filters for alert-only strategy candidates."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from quant_options_monitor.options.models import OptionChain, OptionContract, OptionStrategyCandidate


@dataclass(frozen=True)
class TradeFilterSettings:
    min_option_volume: int = 100
    min_option_open_interest: int = 500
    max_bid_ask_spread_pct: float = 0.15


def is_option_liquid(
    contract: OptionContract,
    min_volume: int,
    min_open_interest: int,
    max_spread_pct: float,
) -> bool:
    """Return whether a contract passes basic liquidity and quote-quality filters."""

    return (
        contract.volume >= min_volume
        and contract.open_interest >= min_open_interest
        and contract.bid > 0
        and contract.ask > contract.bid
        and contract.bid_ask_spread_pct <= max_spread_pct
    )


def filter_liquid_contracts(chain: OptionChain, settings: Any) -> OptionChain:
    """Return a copy of the chain containing only liquid contracts."""

    min_volume = _setting(settings, "min_option_volume")
    min_open_interest = _setting(settings, "min_option_open_interest")
    max_spread_pct = _setting(settings, "max_bid_ask_spread_pct")
    contracts = [
        contract
        for contract in chain.contracts
        if is_option_liquid(contract, min_volume, min_open_interest, max_spread_pct)
    ]
    return chain.model_copy(update={"contracts": contracts})


def validate_strategy_liquidity(
    candidate: OptionStrategyCandidate, settings: Any
) -> tuple[bool, list[str]]:
    """Validate every leg in a candidate and attach human-readable warnings."""

    min_volume = _setting(settings, "min_option_volume")
    min_open_interest = _setting(settings, "min_option_open_interest")
    max_spread_pct = _setting(settings, "max_bid_ask_spread_pct")
    warnings: list[str] = []

    for index, leg in enumerate(candidate.legs, start=1):
        contract = leg.option
        leg_label = f"leg {index} {contract.symbol}"
        if contract.volume < min_volume:
            warnings.append(
                f"{leg_label}: volume {contract.volume} below minimum {min_volume}."
            )
        if contract.open_interest < min_open_interest:
            warnings.append(
                f"{leg_label}: open interest {contract.open_interest} below minimum "
                f"{min_open_interest}."
            )
        if contract.bid <= 0:
            warnings.append(f"{leg_label}: bid must be greater than zero.")
        if contract.ask <= contract.bid:
            warnings.append(
                f"{leg_label}: ask {contract.ask:.2f} must be greater than bid "
                f"{contract.bid:.2f}."
            )
        if contract.bid_ask_spread_pct > max_spread_pct:
            warnings.append(
                f"{leg_label}: bid/ask spread {contract.bid_ask_spread_pct:.2%} exceeds "
                f"maximum {max_spread_pct:.2%}."
            )

    if warnings:
        candidate.warnings.extend(warning for warning in warnings if warning not in candidate.warnings)
    return not warnings, warnings


def _setting(settings: Any, name: str) -> Any:
    if isinstance(settings, dict):
        if name not in settings:
            raise KeyError(f"missing trade filter setting: {name}")
        return settings[name]
    if hasattr(settings, name):
        return getattr(settings, name)
    raise AttributeError(f"missing trade filter setting: {name}")
