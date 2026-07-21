"""Temporal split and leakage-control helpers."""

from __future__ import annotations

import pandas as pd


def assert_strict_prior(
    frame: pd.DataFrame,
    *,
    source_date_col: str = "source_max_date",
    target_date_col: str = "game_date",
) -> None:
    """Fail when any feature source date is on or after the target date."""

    source = pd.to_datetime(frame[source_date_col])
    target = pd.to_datetime(frame[target_date_col])
    bad = frame.loc[source >= target]
    if not bad.empty:
        raise ValueError(f"strict-prior violation in {len(bad)} rows")


def most_recent_training_rows(
    frame: pd.DataFrame,
    *,
    cutoff_date: str,
    n_rows: int,
    date_col: str = "game_date",
) -> pd.DataFrame:
    """Return the most recent rows strictly before a cutoff date."""

    if n_rows <= 0:
        raise ValueError("n_rows must be positive")
    dates = pd.to_datetime(frame[date_col])
    eligible = frame.loc[dates < pd.Timestamp(cutoff_date)].copy()
    eligible = eligible.sort_values([date_col]).tail(n_rows)
    if len(eligible) < n_rows:
        raise ValueError(f"requested {n_rows} rows but found {len(eligible)}")
    return eligible
