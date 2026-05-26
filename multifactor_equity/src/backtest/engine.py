from __future__ import annotations

import pandas as pd

from src.backtest.costs import calculate_turnover, trading_cost
from src.data.providers.base import FundamentalDataProvider, MetadataProvider, PriceData
from src.data.universe import build_eligible_universe_from_providers
from src.factors.composite import compute_factor_scores
from src.portfolio.rebalance import build_target_weights
from src.utils.calendar import month_end_signal_dates, next_trading_day


class BacktestEngine:
    def __init__(
        self,
        price_data: PriceData,
        fundamental_provider: FundamentalDataProvider,
        metadata_provider: MetadataProvider,
        config: dict,
    ):
        self.close = price_data.close
        self.volume = price_data.volume
        self.fundamental_provider = fundamental_provider
        self.metadata_provider = metadata_provider
        self.fundamentals = fundamental_provider.load_fundamentals()
        self.config = config

    def run(self) -> dict[str, pd.DataFrame]:
        dates = self.close.index
        signal_dates = month_end_signal_dates(dates)
        exec_by_signal = {d: next_trading_day(dates, d) for d in signal_dates}
        exec_by_signal = {s: e for s, e in exec_by_signal.items() if e is not None}
        target_by_exec = {}
        factor_frames = []
        universe_members = {}
        rebalance_rows = []
        trades = []
        old_weights = pd.Series(dtype=float)
        for signal_date, exec_date in exec_by_signal.items():
            universe = build_eligible_universe_from_providers(
                signal_date,
                self.close,
                self.volume,
                self.fundamental_provider,
                self.metadata_provider,
                self.config["universe"],
            )
            if universe.empty:
                target = pd.Series(dtype=float)
                scores = pd.DataFrame()
            else:
                scores = compute_factor_scores(signal_date, self.close, universe, self.config)
                target = build_target_weights(scores, self.config["portfolio"])
            factor_frames.append(scores)
            universe_members[exec_date] = list(universe.index)
            target_by_exec[exec_date] = target
            turnover = calculate_turnover(target, old_weights)
            costs = trading_cost(turnover, **self.config["costs"])
            rebalance_rows.append(
                {
                    "signal_date": signal_date,
                    "execution_date": exec_date,
                    "selected_count": int((target > 0).sum()),
                    "target_weight_sum": target.sum(),
                    "turnover": turnover,
                    **costs,
                }
            )
            for ticker in target.index.union(old_weights.index):
                delta = target.get(ticker, 0.0) - old_weights.get(ticker, 0.0)
                if abs(delta) > 1e-12:
                    trades.append({"date": exec_date, "ticker": ticker, "weight_change": delta})
            old_weights = target
        returns = self.close.pct_change(fill_method=None).fillna(0.0)
        weights = pd.DataFrame(0.0, index=dates, columns=self.close.columns)
        daily = pd.Series(0.0, index=dates)
        costs_by_date = {r["execution_date"]: r["total_cost"] for r in rebalance_rows}
        current = pd.Series(dtype=float)
        for i, date in enumerate(dates):
            if date in target_by_exec:
                current = target_by_exec[date]
            if not current.empty:
                available = [t for t in current.index if t in returns.columns]
                weights.loc[date, available] = current.loc[available]
                daily.loc[date] = (returns.loc[date, available] * current.loc[available]).sum()
            daily.loc[date] -= costs_by_date.get(date, 0.0)
        equity = (1 + daily).cumprod() * self.config["initial_capital"]
        positions = weights.stack().rename("weight").reset_index().rename(columns={"level_0": "date", "level_1": "ticker"})
        positions = positions[positions["weight"] > 0]
        sector_map = self.fundamentals.sort_values("available_date").groupby("ticker")["sector"].last().to_dict()
        exposure_rows = []
        for date in dates:
            row = {"date": date}
            active = weights.loc[date]
            for ticker, weight in active[active > 0].items():
                sector = sector_map.get(ticker, "Unknown")
                row[sector] = row.get(sector, 0.0) + weight
            exposure_rows.append(row)
        return {
            "equity_curves": pd.DataFrame({"date": dates, "strategy": equity.values}).set_index("date"),
            "daily_returns": pd.DataFrame({"date": dates, "strategy": daily.values}).set_index("date"),
            "positions": positions,
            "trades": pd.DataFrame(trades),
            "rebalance_log": pd.DataFrame(rebalance_rows),
            "factor_scores": pd.concat(factor_frames) if factor_frames else pd.DataFrame(),
            "sector_exposure": pd.DataFrame(exposure_rows).fillna(0.0),
            "universe_members": universe_members,
        }
