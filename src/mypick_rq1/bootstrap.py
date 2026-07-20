"""Paired date-cluster bootstrap for probability-loss differences."""

from __future__ import annotations

import numpy as np
import pandas as pd


def _binary_log_loss(y: np.ndarray, p: np.ndarray) -> np.ndarray:
    p = np.clip(p, 1e-12, 1 - 1e-12)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def paired_date_bootstrap(
    frame: pd.DataFrame,
    *,
    y_col: str,
    full_probability_col: str,
    baseline_probability_col: str,
    date_col: str,
    reps: int = 20_000,
    random_seed: int = 20260720,
) -> dict[str, float]:
    """Bootstrap mean paired Log-loss differences by game date."""

    work = frame[[date_col, y_col, full_probability_col, baseline_probability_col]].copy()
    y = work[y_col].to_numpy(dtype=float)
    full = work[full_probability_col].to_numpy(dtype=float)
    base = work[baseline_probability_col].to_numpy(dtype=float)
    work["delta"] = _binary_log_loss(y, full) - _binary_log_loss(y, base)
    by_date = work.groupby(date_col, sort=True)["delta"].mean().to_numpy()

    rng = np.random.default_rng(random_seed)
    samples = np.empty(reps, dtype=float)
    for i in range(reps):
        samples[i] = rng.choice(by_date, size=len(by_date), replace=True).mean()

    return {
        "delta_log_loss_full_minus_baseline": float(by_date.mean()),
        "ci_low": float(np.quantile(samples, 0.025)),
        "ci_high": float(np.quantile(samples, 0.975)),
        "improvement_probability": float(np.mean(samples < 0)),
        "reps": int(reps),
    }
