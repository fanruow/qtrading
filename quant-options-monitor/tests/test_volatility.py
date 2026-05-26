from __future__ import annotations

import pandas as pd
import pytest

from src.features.volatility import iv_percentile, iv_rank, iv_realized_spread, term_structure_score


def test_volatility_features() -> None:
    history = pd.Series([0.10, 0.20, 0.30, 0.40])
    assert iv_rank(0.25, history) == pytest.approx(0.5)
    assert iv_percentile(0.30, history) == pytest.approx(0.75)
    assert iv_realized_spread(0.30, 0.20) == pytest.approx(0.10)
    assert term_structure_score(0.20, 0.25) == pytest.approx(0.20)
