"""LightGBM model wrappers and walk-forward validation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, mean_squared_error


Task = Literal["classification", "regression"]


@dataclass(frozen=True)
class WalkForwardResult:
    scores: list[float]
    predictions: pd.Series

    @property
    def mean_score(self) -> float:
        return float(np.mean(self.scores)) if self.scores else float("nan")


class LightGBMModel:
    """Small wrapper around LightGBM classifier/regressor."""

    def __init__(self, task: Task = "classification", **params: object) -> None:
        self.task = task
        if task == "classification":
            from lightgbm import LGBMClassifier

            self.model = LGBMClassifier(random_state=42, n_estimators=100, **params)
        else:
            from lightgbm import LGBMRegressor

            self.model = LGBMRegressor(random_state=42, n_estimators=100, **params)

    def fit(self, x: pd.DataFrame, y: pd.Series) -> "LightGBMModel":
        self.model.fit(x, y)
        return self

    def predict(self, x: pd.DataFrame) -> np.ndarray:
        return self.model.predict(x)


def walk_forward_validation(
    features: pd.DataFrame,
    target: pd.Series,
    task: Task = "classification",
    min_train_size: int = 120,
    test_size: int = 20,
) -> WalkForwardResult:
    """Evaluate a LightGBM model with expanding-window walk-forward splits."""

    scores: list[float] = []
    predictions: list[pd.Series] = []
    for start in range(min_train_size, len(features) - test_size + 1, test_size):
        train_x = features.iloc[:start]
        train_y = target.iloc[:start]
        test_x = features.iloc[start : start + test_size]
        test_y = target.iloc[start : start + test_size]
        model = LightGBMModel(task=task).fit(train_x, train_y)
        pred = pd.Series(model.predict(test_x), index=test_x.index)
        predictions.append(pred)
        if task == "classification":
            scores.append(float(accuracy_score(test_y, pred)))
        else:
            scores.append(float(mean_squared_error(test_y, pred, squared=False)))
    combined = pd.concat(predictions) if predictions else pd.Series(dtype=float)
    return WalkForwardResult(scores=scores, predictions=combined)
