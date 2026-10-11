"""Simple equity signal backtester."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from quant_options_monitor.backtest.metrics import calculate_metrics
from quant_options_monitor.features.pipeline import build_technical_features
from quant_options_monitor.strategies.equity_signal import EquitySignalEngine


@dataclass(frozen=True)
class EquityBacktestResult:
    features: pd.DataFrame
    signals: pd.Series
    positions: pd.Series
    strategy_returns: pd.Series
    equity_curve: pd.Series
    metrics: dict[str, float | int]


class EquitySignalBacktester:
    """Backtest the equity signal engine with next-bar execution."""

    def __init__(
        self,
        initial_capital: float = 100_000.0,
        transaction_cost_bps: float = 1.0,
        allow_short: bool = True,
    ) -> None:
        self.initial_capital = initial_capital
        self.transaction_cost_bps = transaction_cost_bps
        self.allow_short = allow_short
        self.signal_engine = EquitySignalEngine()

    def run(self, symbol: str, ohlcv: pd.DataFrame) -> EquityBacktestResult:
        if ohlcv.empty:
            raise ValueError("ohlcv must not be empty")

        features = build_technical_features(ohlcv)
        raw_positions = self._generate_positions(symbol, features)
        positions = raw_positions.shift(1).fillna(0.0)
        close_returns = ohlcv["close"].pct_change().fillna(0.0)
        turnover = positions.diff().abs().fillna(positions.abs())
        costs = turnover * (self.transaction_cost_bps / 10_000)
        strategy_returns = positions * close_returns - costs
        equity_curve = self.initial_capital * (1 + strategy_returns).cumprod()
        metrics = calculate_metrics(equity_curve, strategy_returns, positions)
        return EquityBacktestResult(
            features=features,
            signals=raw_positions,
            positions=positions,
            strategy_returns=strategy_returns,
            equity_curve=equity_curve,
            metrics=metrics,
        )

    def _generate_positions(self, symbol: str, features: pd.DataFrame) -> pd.Series:
        positions: list[float] = []
        for row_number in range(len(features)):
            as_of_features = features.iloc[: row_number + 1]
            signal = self.signal_engine.generate(symbol, as_of_features)
            if signal.signal_type == "BUY_BIAS":
                positions.append(1.0)
            elif signal.signal_type == "SELL_BIAS" and self.allow_short:
                positions.append(-1.0)
            else:
                positions.append(0.0)
        return pd.Series(positions, index=features.index, name="signal_position")
