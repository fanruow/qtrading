import numpy as np
import pandas as pd

from src.benchmarks import monthly_rebalanced_static_portfolio


def test_monthly_rebalanced_static_portfolio_enters_on_execution_dates():
    dates = pd.bdate_range("2023-01-30", periods=5)
    returns = pd.DataFrame({"SPY": 0.01, "IEF": 0.0}, index=dates)

    portfolio_returns = monthly_rebalanced_static_portfolio(
        returns,
        {"SPY": 0.6, "IEF": 0.4},
        "60/40",
    )

    assert portfolio_returns.loc[pd.Timestamp("2023-01-31")] == 0.0
    assert np.isclose(portfolio_returns.loc[pd.Timestamp("2023-02-01")], 0.006)
