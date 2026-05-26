"""Options data provider abstraction."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

from quant_options_monitor.options.models import OptionChain


class BaseOptionsProvider(ABC):
    """Typed interface for options chain providers."""

    @abstractmethod
    def get_chain(self, symbol: str) -> OptionChain:
        """Return a normalized option chain for the underlying symbol."""

    @abstractmethod
    def get_expirations(self, symbol: str) -> list[date]:
        """Return available expiration dates for the underlying symbol."""
