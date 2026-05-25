from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import pandas as pd


@dataclass
class PriceData:
    open: pd.DataFrame
    high: pd.DataFrame
    low: pd.DataFrame
    close: pd.DataFrame
    volume: pd.DataFrame

    def validate(self) -> None:
        frames = {
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
        }
        index = self.close.index
        columns = list(self.close.columns)
        for name, frame in frames.items():
            if not isinstance(frame, pd.DataFrame):
                raise TypeError(f"PriceData.{name} must be a pandas DataFrame")
            if not frame.index.equals(index):
                raise ValueError(f"PriceData.{name} index must match close index")
            if list(frame.columns) != columns:
                raise ValueError(f"PriceData.{name} columns must match close columns")


class PriceDataProvider(ABC):
    @abstractmethod
    def load_prices(self, tickers: list[str], start: str, end: str) -> PriceData:
        raise NotImplementedError


class FundamentalDataProvider(ABC):
    @abstractmethod
    def load_fundamentals(self) -> pd.DataFrame:
        raise NotImplementedError

    def fundamentals_asof(self, as_of: pd.Timestamp) -> pd.DataFrame:
        fundamentals = self.load_fundamentals()
        eligible = fundamentals[fundamentals["available_date"] <= pd.Timestamp(as_of)].copy()
        eligible = eligible.sort_values(["ticker", "available_date", "report_date"])
        return eligible.groupby("ticker", as_index=False).tail(1).set_index("ticker", drop=False)


class MetadataProvider(ABC):
    @abstractmethod
    def load_metadata(self) -> pd.DataFrame:
        raise NotImplementedError

    def metadata_asof(self, as_of: pd.Timestamp) -> pd.DataFrame:
        metadata = self.load_metadata()
        if "available_date" not in metadata.columns:
            return metadata.set_index("ticker", drop=False)
        eligible = metadata[metadata["available_date"] <= pd.Timestamp(as_of)].copy()
        eligible = eligible.sort_values(["ticker", "available_date"])
        return eligible.groupby("ticker", as_index=False).tail(1).set_index("ticker", drop=False)
