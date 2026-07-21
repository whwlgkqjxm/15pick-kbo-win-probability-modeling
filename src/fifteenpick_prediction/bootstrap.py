"""Date-cluster bootstrap matching the authoritative V12 implementation."""

from __future__ import annotations

import numpy as np
import pandas as pd


def binary_log_loss_rows(y: np.ndarray, p: np.ndarray) -> np.ndarray:
    p = np.clip(np.asarray(p, dtype=float), 1e-6, 1 - 1e-6)
    y = np.asarray(y, dtype=int)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def paired_date_bootstrap(
    frame: pd.DataFrame,
    *,
    new_probability_col: str,
    reference_probability_col: str,
    date_col: str = "game_date",
    target_col: str = "home_win",
    reps: int = 10_000,
    rng: np.random.Generator | None = None,
    random_seed: int = 20260720,
) -> dict[str, float | int | str]:
    """Resample dates, concatenate all games on sampled dates, and compare Log loss.

    Resampling game rows independently would ignore within-date dependence. Averaging
    date-level deltas before resampling would give every date equal weight even when
    dates contain different numbers of games. The authoritative study instead samples
    dates and then concatenates every game belonging to each sampled date.
    """
    required = {date_col, target_col, new_probability_col, reference_probability_col}
    missing = required - set(frame.columns)
    if missing:
        raise KeyError(f"missing columns: {sorted(missing)}")
    if reps <= 0:
        raise ValueError("reps must be positive")

    work = frame.loc[:, list(required)].copy()
    y = work[target_col].to_numpy(dtype=int)
    new_loss = binary_log_loss_rows(y, work[new_probability_col].to_numpy(float))
    ref_loss = binary_log_loss_rows(y, work[reference_probability_col].to_numpy(float))
    dates = work[date_col].to_numpy()
    unique_dates = np.array(sorted(np.unique(dates)))
    index_by_date = {date: np.flatnonzero(dates == date) for date in unique_dates}
    generator = rng if rng is not None else np.random.default_rng(random_seed)

    differences = np.empty(reps, dtype=float)
    for i in range(reps):
        sampled_dates = generator.choice(unique_dates, size=len(unique_dates), replace=True)
        sampled_index = np.concatenate([index_by_date[date] for date in sampled_dates])
        differences[i] = np.mean(new_loss[sampled_index] - ref_loss[sampled_index])

    return {
        "new_model": new_probability_col,
        "reference_model": reference_probability_col,
        "delta_log_loss": float(np.mean(new_loss - ref_loss)),
        "ci_low": float(np.quantile(differences, 0.025)),
        "ci_high": float(np.quantile(differences, 0.975)),
        "improvement_probability": float(np.mean(differences < 0)),
        "reps": int(reps),
    }
