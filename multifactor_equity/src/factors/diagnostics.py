from __future__ import annotations

import pandas as pd


FACTOR_COLUMNS = ["momentum_score", "quality_score", "value_score", "low_vol_score", "composite_score"]


def spearman_rank_corr(x: pd.Series, y: pd.Series) -> float:
    return x.rank().corr(y.rank())


def forward_returns(close: pd.DataFrame, signal_date: pd.Timestamp, next_signal_date: pd.Timestamp, tickers: list[str]) -> pd.Series:
    return close.loc[next_signal_date, tickers] / close.loc[signal_date, tickers] - 1


def compute_factor_diagnostics(factor_scores: pd.DataFrame, close: pd.DataFrame, quantiles: int = 5) -> tuple[pd.DataFrame, pd.DataFrame]:
    if factor_scores.empty:
        return pd.DataFrame(), pd.DataFrame()
    factor_scores = factor_scores.copy()
    factor_scores["signal_date"] = pd.to_datetime(factor_scores["signal_date"])
    dates = sorted(factor_scores["signal_date"].unique())
    ic_rows = []
    q_rows = []
    for i, signal_date in enumerate(dates[:-1]):
        next_date = dates[i + 1]
        cross = factor_scores[factor_scores["signal_date"] == signal_date].set_index("ticker")
        tickers = [t for t in cross.index if t in close.columns]
        fwd = forward_returns(close, signal_date, next_date, tickers)
        for factor in FACTOR_COLUMNS:
            aligned = pd.concat([cross.loc[tickers, factor], fwd.rename("forward_return")], axis=1).dropna()
            if len(aligned) >= 3:
                ic = spearman_rank_corr(aligned[factor], aligned["forward_return"])
                try:
                    buckets = pd.qcut(aligned[factor].rank(method="first"), quantiles, labels=False) + 1
                    grouped = aligned.groupby(buckets)["forward_return"].mean()
                    for q, val in grouped.items():
                        q_rows.append({"signal_date": signal_date, "factor": factor, "quantile": int(q), "forward_return": val})
                    if 1 in grouped.index and quantiles in grouped.index:
                        q_rows.append({"signal_date": signal_date, "factor": factor, "quantile": "top_minus_bottom", "forward_return": grouped.loc[quantiles] - grouped.loc[1]})
                except ValueError:
                    pass
            else:
                ic = pd.NA
            ic_rows.append({"signal_date": signal_date, "factor": factor, "ic": ic})
    ic_df = pd.DataFrame(ic_rows)
    if not ic_df.empty:
        stats = ic_df.groupby("factor")["ic"].agg(["mean", "std"]).rename(columns={"mean": "ic_mean", "std": "ic_std"})
        stats["icir"] = stats["ic_mean"] / stats["ic_std"]
        ic_df = ic_df.merge(stats, on="factor", how="left")
    return ic_df, pd.DataFrame(q_rows)
