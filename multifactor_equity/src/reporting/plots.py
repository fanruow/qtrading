from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from src.backtest.metrics import drawdown


def save_equity_curve(equity: pd.DataFrame, path: str | Path) -> None:
    ax = equity.plot(figsize=(10, 5), title="Equity Curve")
    ax.set_ylabel("Equity")
    plt.tight_layout()
    plt.savefig(path)
    plt.close()


def save_drawdown(equity: pd.Series, path: str | Path) -> None:
    ax = drawdown(equity).plot(figsize=(10, 4), title="Drawdown")
    ax.set_ylabel("Drawdown")
    plt.tight_layout()
    plt.savefig(path)
    plt.close()


def save_factor_ic(ic: pd.DataFrame, path: str | Path) -> None:
    if ic.empty:
        return
    pivot = ic.pivot(index="signal_date", columns="factor", values="ic")
    ax = pivot.plot(figsize=(10, 5), title="Factor IC")
    ax.axhline(0, color="black", linewidth=0.8)
    plt.tight_layout()
    plt.savefig(path)
    plt.close()
