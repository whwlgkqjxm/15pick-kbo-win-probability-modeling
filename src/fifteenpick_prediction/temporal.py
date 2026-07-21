"""Temporal ordering, split, and leakage-control helpers."""

from __future__ import annotations

import pandas as pd


def stable_temporal_sort(
    frame: pd.DataFrame, *, date_col: str = "game_date", id_col: str = "game_id"
) -> pd.DataFrame:
    """Return a deterministic chronological order using date and game ID."""
    if date_col not in frame.columns:
        raise KeyError(f"missing column: {date_col}")
    columns = [date_col, id_col] if id_col in frame.columns else [date_col]
    return frame.sort_values(columns, kind="mergesort").reset_index(drop=True)


def assert_strict_prior(
    frame: pd.DataFrame,
    *,
    source_date_col: str = "source_max_date",
    target_date_col: str = "game_date",
) -> None:
    """Fail when any feature source date is on or after the target date."""
    source = pd.to_datetime(frame[source_date_col].astype(str))
    target = pd.to_datetime(frame[target_date_col].astype(str))
    bad = frame.loc[source >= target]
    if not bad.empty:
        raise ValueError(f"strict-prior violation in {len(bad)} rows")


def most_recent_training_rows(
    frame: pd.DataFrame,
    *,
    cutoff_date: int | str,
    n_rows: int,
    date_col: str = "game_date",
    id_col: str = "game_id",
) -> pd.DataFrame:
    """Select the last N decision games strictly before a cutoff, deterministically."""
    if n_rows <= 0:
        raise ValueError("n_rows must be positive")
    ordered = stable_temporal_sort(frame, date_col=date_col, id_col=id_col)
    cutoff = pd.to_datetime(str(cutoff_date))
    dates = pd.to_datetime(ordered[date_col].astype(str))
    eligible = ordered.loc[dates < cutoff]
    if len(eligible) < n_rows:
        raise ValueError(f"requested {n_rows} rows but found {len(eligible)}")
    return eligible.tail(n_rows).copy()
