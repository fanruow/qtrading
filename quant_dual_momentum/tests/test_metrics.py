import numpy as np
import pandas as pd

from src.metrics import cagr, max_drawdown


def test_max_drawdown_calculation_is_correct():
    equity = pd.Series([1.0, 1.2, 0.9, 1.1])

    assert np.isclose(max_drawdown(equity), -0.25)


def test_cagr_calculation_is_correct():
    equity = pd.Series(np.linspace(1.0, 1.21, 253))

    assert np.isclose(cagr(equity), 0.21)
