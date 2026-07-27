"""Date-cluster bootstrap matching the authoritative V12 implementation."""

from __future__ import annotations

import numpy as np
import pandas as pd

_PROBABILITY_EPSILON = 1e-6


def binary_log_loss_rows(y: np.ndarray, p: np.ndarray) -> np.ndarray:
    """Return one binary Log loss value per row after fail-closed validation."""
    y_array = np.asarray(y)
    try:
        p_array = np.asarray(p, dtype=float)
    except (TypeError, ValueError) as exc:
        raise ValueError("probabilities must be numeric") from exc

    if y_array.ndim != 1 or p_array.ndim != 1:
        raise ValueError("targets and probabilities must be one-dimensional")
    if y_array.size == 0:
        raise ValueError("targets and probabilities must contain at least one value")
    if y_array.shape != p_array.shape:
        raise ValueError("targets and probabilities must have the same shape")
    if pd.isna(y_array).any() or not np.isin(y_array, [0, 1]).all():
        raise ValueError("targets must contain only binary values 0 and 1")
    if not np.isfinite(p_array).all():
        raise ValueError("probabilities must be finite")
    if ((p_array < 0) | (p_array > 1)).any():
        raise ValueError("probabilities must lie in the closed interval [0, 1]")

    y_binary = y_array.astype(int, copy=False)
    p_clipped = np.clip(p_array, _PROBABILITY_EPSILON, 1 - _PROBABILITY_EPSILON)
    return -(y_binary * np.log(p_clipped) + (1 - y_binary) * np.log(1 - p_clipped))


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
    """Resample dates, concatenate their games, and compare paired Log loss.

    Resampling game rows independently would ignore within-date dependence. Averaging
    date-level deltas before resampling would give every date equal weight even when
    dates contain different numbers of games. The authoritative study instead samples
    dates and concatenates every game belonging to each sampled date.

    The returned ``improvement_probability`` is the proportion of bootstrap replicates
    with ``new Log loss - reference Log loss < 0``. It is not a Bayesian posterior
    probability that the new model is superior.
    """
    if not isinstance(frame, pd.DataFrame):
        raise TypeError("frame must be a pandas DataFrame")
    if not frame.columns.is_unique:
        raise ValueError("frame column names must be unique")
    if isinstance(reps, bool) or not isinstance(reps, (int, np.integer)) or reps <= 0:
        raise ValueError("reps must be a positive integer")
    if rng is not None and not isinstance(rng, np.random.Generator):
        raise TypeError("rng must be a numpy.random.Generator or None")

    requested_columns = [
        date_col,
        target_col,
        new_probability_col,
        reference_probability_col,
    ]
    missing = sorted(set(requested_columns) - set(frame.columns))
    if missing:
        raise KeyError(f"missing columns: {missing}")
    if frame.empty:
        raise ValueError("frame must contain at least one row")

    selected_columns = list(dict.fromkeys(requested_columns))
    work = frame.loc[:, selected_columns].copy()
    if work[date_col].isna().any():
        raise ValueError(f"{date_col} must not contain missing values")

    y = work[target_col].to_numpy()
    new_loss = binary_log_loss_rows(y, work[new_probability_col].to_numpy())
    ref_loss = binary_log_loss_rows(y, work[reference_probability_col].to_numpy())
    dates = work[date_col].to_numpy()
    unique_dates = np.array(sorted(np.unique(dates)))
    index_by_date = {date: np.flatnonzero(dates == date) for date in unique_dates}
    generator = rng if rng is not None else np.random.default_rng(random_seed)

    differences = np.empty(int(reps), dtype=float)
    for i in range(int(reps)):
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
