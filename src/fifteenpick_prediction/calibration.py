"""Calibration summaries for probabilistic forecasts."""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression


def logit(probability: np.ndarray) -> np.ndarray:
    p = np.clip(np.asarray(probability, dtype=float), 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def calibration_intercept_slope(y_true, probability) -> dict[str, float]:
    """Estimate calibration intercept and slope using a logistic recalibration model."""
    y = np.asarray(y_true, dtype=int)
    x = logit(np.asarray(probability, dtype=float)).reshape(-1, 1)
    model = LogisticRegression(C=1e6, max_iter=10000)
    model.fit(x, y)
    return {
        "calibration_intercept": float(model.intercept_[0]),
        "calibration_slope": float(model.coef_[0, 0]),
    }


def calibration_table(y_true, probability, bins: int = 10) -> pd.DataFrame:
    """Return equal-frequency reliability bins."""
    p = np.asarray(probability, dtype=float)
    y = np.asarray(y_true, dtype=int)
    q = pd.qcut(pd.Series(p), q=bins, duplicates="drop")
    frame = pd.DataFrame({"y": y, "p": p, "bin": q})
    out = (
        frame.groupby("bin", observed=True)
        .agg(n=("y", "size"), predicted_mean=("p", "mean"), actual_rate=("y", "mean"))
        .reset_index()
    )
    out["abs_gap"] = (out["predicted_mean"] - out["actual_rate"]).abs()
    return out
