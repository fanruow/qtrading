"""Plotting helpers for backtest outputs."""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", str(Path.cwd() / ".matplotlib"))
import matplotlib.pyplot as plt
import pandas as pd

from .metrics import drawdown


def plot_equity_curves(equity_curves: pd.DataFrame, output_path: str | Path) -> None:
    """Plot strategy and benchmark equity curves."""
    ax = equity_curves.plot(figsize=(12, 7), linewidth=1.5)
    ax.set_title("Equity Curves")
    ax.set_ylabel("Growth of $1")
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()


def plot_drawdowns(equity_curves: pd.DataFrame, output_path: str | Path) -> None:
    """Plot drawdown curves for strategy and benchmarks."""
    dd = equity_curves.apply(drawdown)
    ax = dd.plot(figsize=(12, 7), linewidth=1.3)
    ax.set_title("Drawdown")
    ax.set_ylabel("Drawdown")
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()
