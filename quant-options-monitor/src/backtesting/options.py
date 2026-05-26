"""Options strategy simulation placeholder."""

from __future__ import annotations

from src.data.models import StrategyCandidate


def simulate_options_strategy(candidate: StrategyCandidate) -> dict[str, object]:
    """Return a structured placeholder for future path-aware options simulation."""

    return {
        "strategy": candidate.strategy,
        "status": "stub",
        "message": "Path-aware options pricing and assignment simulation is planned after v1 alerts.",
    }
